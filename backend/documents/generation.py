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

from .letters import eligibility_context, process_list_context
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
            # A regenerated letter supersedes the last one — the old PDF is soft-deleted, never
            # overwritten, so the audit trail keeps what was previously sent out (§6.6).
            superseded = list(
                Document.objects.filter(
                    process=job.process, document_type=ELIGIBILITY_DOC_TYPE
                ).values_list("id", flat=True)
            )
            Document.objects.filter(id__in=superseded).update(
                is_deleted=True, deleted_at=timezone.now(), deleted_by=job.requested_by
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
            record_activity(
                actor=job.requested_by,
                action=ActivityLog.Action.CREATE,
                entity_type="GenerationJob",
                entity_id=job.id,
                after={
                    "kind": job.kind,
                    "process_id": job.process_id,
                    "template_id": job.template_id,
                    "document_id": document.id,
                    "superseded_document_ids": superseded,
                },
            )
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
        record_activity(
            actor=job.requested_by,
            action=ActivityLog.Action.CREATE,
            entity_type="GenerationJob",
            entity_id=job.id,
            after={
                "kind": job.kind,
                "template_id": job.template_id,
                "process_ids": job.process_ids,
                "count": len(processes),
            },
        )
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


def start_eligibility_job(*, process, actor, template_id=None) -> GenerationJob:
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
    # on_commit: the worker must never look up a job row this transaction has not committed yet.
    transaction.on_commit(lambda: generate_eligibility.delay(job.id))
    return job


def start_process_list_job(*, process_ids, actor, template_id=None) -> GenerationJob:
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
    transaction.on_commit(lambda: generate_process_list.delay(job.id))
    return job
