"""Template → PDF generation services (§6.6, §6.8) — the sole place that writes generation audit.

Runs inside the Celery worker: `docxtpl` fills the stored `.docx`, headless LibreOffice renders
it, and the result becomes either a `Document` on the process (single letter) or a standalone
file the requester downloads (list letter, which spans several people and so belongs to none).
"""

import tempfile
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from docxtpl import DocxTemplate

from common.models import ActivityLog
from common.services import record_activity
from processes.models import Process

from .letters import eligibility_context, process_codes_context, process_list_context
from .models import Document, DocumentTemplate, GenerationJob
from .rendering import RenderError, docx_to_pdf
from .services import create_document

# Generated letters are Step-1 output and carry this controlled type (§6.7).
ELIGIBILITY_DOC_TYPE = "EligibilityLetter"
# List letters span people, so they live outside the per-person tree (§6.8).
GENERATED_LISTS_DIR = "_generated/lists"


def render_to_pdf(template: DocumentTemplate, context: dict, out_dir: Path) -> bytes:
    """Fill the template and render it, returning the PDF bytes."""
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


def run_eligibility_job(job_id: int) -> None:
    """Generate the single-beneficiary letter and attach it to the process."""
    job = GenerationJob.objects.select_related("process__client", "template").get(pk=job_id)
    job.status = GenerationJob.Status.RUNNING
    job.save(update_fields=["status", "updated_at"])

    try:
        with tempfile.TemporaryDirectory(prefix="gen-") as work:
            pdf = render_to_pdf(job.template, eligibility_context(job.process), Path(work))

        with transaction.atomic():
            # Same lock as the compiled export: two concurrent regenerations would otherwise
            # both leave a live letter on the case.
            Process.objects.select_for_update().get(pk=job.process_id)
            # A regenerated letter supersedes the last one — the old PDF is soft-deleted, never
            # overwritten, so the audit trail keeps what was previously sent out (§6.6).
            for old in Document.objects.filter(
                process=job.process, document_type=ELIGIBILITY_DOC_TYPE
            ):
                old.is_deleted = True
                old.deleted_at = timezone.now()
                old.deleted_by = job.requested_by
                old.version += 1
                old.save(
                    update_fields=["is_deleted", "deleted_at", "deleted_by", "version"]
                )
                record_activity(
                    actor=job.requested_by,
                    action=ActivityLog.Action.DELETE,
                    entity_type="Document",
                    entity_id=old.pk,
                    before={"display_filename": old.display_filename, "superseded_by_job": job.id},
                )
            document = create_document(
                process=job.process,
                step_number=1,
                document_type=ELIGIBILITY_DOC_TYPE,
                input_source=Document.InputSource.SYSTEM_GENERATED,
                content=pdf,
                actor=job.requested_by,
            )
            job.document = document
            job.status = GenerationJob.Status.DONE
            job.save(update_fields=["document", "status", "updated_at"])
    except Exception as exc:  # a failed render must never look like a success
        _fail(job, str(exc))
        raise


def run_process_list_job(job_id: int) -> None:
    """Generate the multi-beneficiary list letter as a standalone downloadable file."""
    job = GenerationJob.objects.select_related("template").get(pk=job_id)
    job.status = GenerationJob.Status.RUNNING
    job.save(update_fields=["status", "updated_at"])

    try:
        # Re-read the rows here, in the order requested, so the letter reflects the data as it is
        # now rather than as it was when the button was pressed.
        by_id = Process.objects.select_related("client").in_bulk(job.process_ids)
        processes = [by_id[pid] for pid in job.process_ids if pid in by_id]
        if not processes:
            raise RenderError("None of the selected allocations are available any more.")

        with tempfile.TemporaryDirectory(prefix="gen-") as work:
            pdf = render_to_pdf(job.template, process_list_context(processes), Path(work))

        destination = Path(settings.DOCUMENTS_ROOT) / GENERATED_LISTS_DIR
        destination.mkdir(parents=True, exist_ok=True)
        out_file = destination / f"list_{job.id}.pdf"
        out_file.write_bytes(pdf)

        job.output_path = f"{GENERATED_LISTS_DIR}/{out_file.name}"
        job.status = GenerationJob.Status.DONE
        job.save(update_fields=["output_path", "status", "updated_at"])
    except Exception as exc:
        _fail(job, str(exc))
        raise


def run_process_codes_job(job_id: int) -> None:
    """Generate the code list (§6.8, UC-057) — the office's own form of number/name/code/land."""
    job = GenerationJob.objects.select_related("template").get(pk=job_id)
    job.status = GenerationJob.Status.RUNNING
    job.save(update_fields=["status", "updated_at"])

    try:
        # Re-read in the order requested, so the form reflects the data as it is now.
        by_id = Process.objects.select_related("client").in_bulk(job.process_ids)
        processes = [by_id[pid] for pid in job.process_ids if pid in by_id]
        if not processes:
            raise RenderError("None of the selected allocations are available any more.")

        with tempfile.TemporaryDirectory(prefix="gen-") as work:
            pdf = render_to_pdf(job.template, process_codes_context(processes), Path(work))

        destination = Path(settings.DOCUMENTS_ROOT) / GENERATED_LISTS_DIR
        destination.mkdir(parents=True, exist_ok=True)
        out_file = destination / f"codes_{job.id}.pdf"
        out_file.write_bytes(pdf)

        job.output_path = f"{GENERATED_LISTS_DIR}/{out_file.name}"
        job.status = GenerationJob.Status.DONE
        job.save(update_fields=["output_path", "status", "updated_at"])
    except Exception as exc:
        _fail(job, str(exc))
        raise


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
