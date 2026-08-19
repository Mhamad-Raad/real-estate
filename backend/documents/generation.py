"""Template → PDF generation services (§6.6, §6.8) — the sole place that writes generation audit.

Runs inside the Celery worker: `docxtpl` fills the stored `.docx`, headless LibreOffice renders
it, and the result becomes a standalone file the requester downloads. Nothing generated here is
filed on a case — the list letters span several people and so belong to none, and the Step-1
letter is produced to be read and printed rather than archived (UC-075).
"""

import tempfile
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from docxtpl import DocxTemplate

from common.models import ActivityLog
from common.services import record_activity
from processes.models import Process

from .letters import eligibility_context, process_codes_context, process_list_context
from .models import DocumentTemplate, GenerationJob
from .rendering import RenderError, docx_to_pdf

# Both live under `settings.GENERATED_ROOT`, which is **outside the office's archive** (UC-101):
# a list spans people so it belongs to no case folder (§6.8), and the Step-1 letter is produced to
# be read and printed rather than archived (UC-075). Neither is ever a Document on a case.
GENERATED_LISTS_DIR = "lists"
GENERATED_LETTERS_DIR = "letters"


def render_to_pdf(template: DocumentTemplate, context: dict, out_dir: Path) -> bytes:
    """Fill the template and render it, returning the PDF bytes."""
    # A blank form carries no placeholders and is not a `.docx` at all (§6.6); docxtpl would fail
    # here with an unreadable-zip error. Refused at the choke point every render passes through,
    # so a future job kind cannot wire one up by mistake.
    if template.is_blank_form:
        raise RenderError(f"'{template.template_type}' is a blank form and is never filled in.")
    source = Path(settings.LETTER_TEMPLATES_ROOT) / template.file_path
    if not source.is_file():
        raise RenderError(f"Template file is missing on disk: {source}")

    filled = out_dir / "filled.docx"
    document = DocxTemplate(str(source))
    document.render(context)
    document.save(str(filled))
    return docx_to_pdf(filled, out_dir).read_bytes()


def _fail(job: GenerationJob, message: str) -> None:
    job.status = GenerationJob.Status.FAILED
    job.error = message[:2000]
    job.save(update_fields=["status", "error", "updated_at"])


# The generated kinds no case ever points at, and so the only ones whose files are ours to remove.
# `COMPILED_CASE` is deliberately absent: it is filed on the case as a real `Document` (§10.3).
UNFILED_KINDS = (
    GenerationJob.Kind.ELIGIBILITY,
    GenerationJob.Kind.PROCESS_LIST,
    GenerationJob.Kind.PROCESS_CODES,
)


def _discard_stale_output(job: GenerationJob) -> None:
    """Clear out generated files nobody can still be reading (UC-075, UC-096).

    None of these are archived, so nothing on a case ever points at one: the screen forgets the
    job as soon as the lawyer navigates away, and after that the PDF is unreachable. Two things
    go, both file-only — **the job rows always stay**, because they are the record of who
    generated what (§11):

    1. the previous output this one supersedes — for a letter, the same case's earlier copy;
    2. **any** output of this kind older than the retention window, which is what stops the
       directory growing by one permanent file per generation ever run.

    A list letter belongs to no single case (§6.8), so it has no per-case predecessor to supersede
    and age alone retires it. Sweeping the lists at all is the fix for the office finding
    the lists directory growing without bound — it was letters-only before (UC-096).

    Swept here rather than from `CELERY_BEAT_SCHEDULE` on purpose: the office computers are on
    09:00–14:00 and beat does not replay a schedule it slept through, so a nightly sweep would
    never once run. Generating is exactly when these directories grow, so cleaning up at that
    moment keeps them bounded without depending on the scheduler at all.
    """
    if job.kind not in UNFILED_KINDS:
        return
    root = Path(settings.GENERATED_ROOT)
    cutoff = timezone.now() - timedelta(days=settings.GENERATED_OUTPUT_RETENTION_DAYS)
    stale = (
        GenerationJob.objects.filter(kind=job.kind)
        .exclude(pk=job.pk)
        .exclude(output_path="")
    )
    aged = Q(created_at__lt=cutoff)
    stale = stale.filter(Q(process_id=job.process_id) | aged if job.process_id else aged)
    for old in stale:
        (root / old.output_path).unlink(missing_ok=True)


def run_eligibility_job(job_id: int) -> None:
    """Render the single-beneficiary letter to a downloadable file (§6.6, UC-075).

    **Not filed on the case.** The office produces this letter to read and print; keeping a copy
    on every allocation meant it was also merged into the Step-5 compiled export, where they do
    not want it. So it is written like the bulk letters — a standalone job output — and the case
    itself carries no `EligibilityLetter` document.
    """
    job = GenerationJob.objects.select_related("process__client", "template").get(pk=job_id)
    job.status = GenerationJob.Status.RUNNING
    job.save(update_fields=["status", "updated_at"])

    try:
        with tempfile.TemporaryDirectory(prefix="gen-") as work:
            pdf = render_to_pdf(job.template, eligibility_context(job.process), Path(work))

        destination = Path(settings.GENERATED_ROOT) / GENERATED_LETTERS_DIR
        destination.mkdir(parents=True, exist_ok=True)
        out_file = destination / f"letter_{job.id}.pdf"
        out_file.write_bytes(pdf)
        _discard_stale_output(job)

        job.output_path = f"{GENERATED_LETTERS_DIR}/{out_file.name}"
        job.status = GenerationJob.Status.DONE
        job.save(update_fields=["output_path", "status", "updated_at"])
    except Exception as exc:  # a failed render must never look like a success
        _fail(job, str(exc))
        raise


def _run_bulk_job(job_id: int, *, build_context, stem: str) -> None:
    """Render a multi-case document to a standalone downloadable file (§6.8).

    Shared by the list letter and the code list: they differ only in which context the template is
    filled from and what the output file is called. Everything else — re-reading the rows in the
    order requested, the failure handling, where the file lands — is the same, and was duplicated
    line for line until this was extracted.
    """
    job = GenerationJob.objects.select_related("template").get(pk=job_id)
    job.status = GenerationJob.Status.RUNNING
    job.save(update_fields=["status", "updated_at"])

    try:
        # Re-read the rows here, in the order requested, so the document reflects the data as it
        # is now rather than as it was when the button was pressed.
        by_id = Process.objects.select_related("client").in_bulk(job.process_ids)
        processes = [by_id[pid] for pid in job.process_ids if pid in by_id]
        if not processes:
            raise RenderError("None of the selected allocations are available any more.")

        with tempfile.TemporaryDirectory(prefix="gen-") as work:
            pdf = render_to_pdf(job.template, build_context(processes), Path(work))

        destination = Path(settings.GENERATED_ROOT) / GENERATED_LISTS_DIR
        destination.mkdir(parents=True, exist_ok=True)
        out_file = destination / f"{stem}_{job.id}.pdf"
        out_file.write_bytes(pdf)
        _discard_stale_output(job)

        job.output_path = f"{GENERATED_LISTS_DIR}/{out_file.name}"
        job.status = GenerationJob.Status.DONE
        job.save(update_fields=["output_path", "status", "updated_at"])
    except Exception as exc:
        _fail(job, str(exc))
        raise


def run_process_list_job(job_id: int) -> None:
    """Generate the multi-beneficiary list letter as a standalone downloadable file."""
    _run_bulk_job(job_id, build_context=process_list_context, stem="list")


def run_process_codes_job(job_id: int) -> None:
    """Generate the code list (§6.8, UC-057) — the office's own form of number/name/code/land."""
    _run_bulk_job(job_id, build_context=process_codes_context, stem="codes")


def _template_or_400(template_type: str, template_id=None) -> DocumentTemplate:
    if template_id is not None:
        template = DocumentTemplate.objects.filter(
            pk=template_id, template_type=template_type
        ).first()
        if template is None:
            raise ValidationError({"template": "No such template for this letter."})
        return template
    template = DocumentTemplate.objects.filter(
        template_type=template_type, is_active=True
    ).first()
    if template is None:
        raise ValidationError(
            {"template": f"No active '{template_type}' template has been uploaded yet."}
        )
    return template


def _audit_requested(job: GenerationJob, extra: dict, request=None) -> None:
    record_activity(
        actor=job.requested_by,
        action=ActivityLog.Action.GENERATE,
        entity_type="GenerationJob",
        entity_id=job.id,
        after={"kind": job.kind, "template_id": job.template_id, **extra},
        request=request,
    )


def start_eligibility_job(*, process, actor, template_id=None, request=None) -> GenerationJob:
    """Queue the single-beneficiary letter for a process."""
    from .tasks import generate_eligibility

    template = _template_or_400(
        DocumentTemplate.TemplateType.ELIGIBILITY_SINGLE, template_id
    )
    job = GenerationJob.objects.create(
        kind=GenerationJob.Kind.ELIGIBILITY,
        template=template,
        process=process,
        requested_by=actor,
    )
    _audit_requested(job, {"process_id": process.id}, request)
    # on_commit: the worker must never look up a job row this transaction has not committed yet.
    transaction.on_commit(lambda: generate_eligibility.delay(job.id))
    return job


def start_process_list_job(*, process_ids, actor, template_id=None, request=None) -> GenerationJob:
    """Queue the multi-beneficiary list letter for the selected processes."""
    from .tasks import generate_process_list

    template = _template_or_400(DocumentTemplate.TemplateType.PROCESS_LIST, template_id)
    # Re-validate every id server-side so a stale or hidden row cannot be smuggled in (§6.8).
    known = set(Process.objects.filter(pk__in=process_ids).values_list("id", flat=True))
    unknown = [pid for pid in process_ids if pid not in known]
    if unknown:
        raise ValidationError({"process_ids": f"Unknown allocations: {unknown}"})

    job = GenerationJob.objects.create(
        kind=GenerationJob.Kind.PROCESS_LIST,
        template=template,
        process_ids=list(process_ids),
        requested_by=actor,
    )
    # A bulk letter exports personal data for many people — the request itself is the thing that
    # must be traceable, whether or not the render later succeeds (§6.8, §11).
    _audit_requested(job, {"process_ids": job.process_ids, "count": len(job.process_ids)}, request)
    transaction.on_commit(lambda: generate_process_list.delay(job.id))
    return job


# The office prints the code list once a case has reached the institutes, so an earlier one has
# no land number and nothing to report (UC-057).
CODES_MIN_STEP = 3


def start_process_codes_job(*, process_ids, actor, template_id=None, request=None) -> GenerationJob:
    """Queue the code list for the selected processes (§6.8, UC-057)."""
    from .tasks import generate_process_codes

    template = _template_or_400(DocumentTemplate.TemplateType.PROCESS_CODES, template_id)
    # Re-validated server-side, exactly like the list letter: the step gate is a rule, and the UI
    # hiding a button is never the boundary (§7.2).
    rows = Process.objects.filter(pk__in=process_ids).values_list("id", "current_step")
    known = {pid: step for pid, step in rows}
    unknown = [pid for pid in process_ids if pid not in known]
    if unknown:
        raise ValidationError({"process_ids": f"Unknown allocations: {unknown}"})
    too_early = [pid for pid in process_ids if known[pid] < CODES_MIN_STEP]
    if too_early:
        raise ValidationError(
            {"process_ids": f"These allocations have not reached step {CODES_MIN_STEP}: {too_early}"}
        )

    job = GenerationJob.objects.create(
        kind=GenerationJob.Kind.PROCESS_CODES,
        template=template,
        process_ids=list(process_ids),
        requested_by=actor,
    )
    # Same reasoning as the list letter: a bulk export of personal data must be traceable from the
    # moment it is asked for, whether or not the render later succeeds (§6.8, §11).
    _audit_requested(job, {"process_ids": job.process_ids, "count": len(job.process_ids)}, request)
    transaction.on_commit(lambda: generate_process_codes.delay(job.id))
    return job
