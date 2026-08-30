"""Step-5 compiled case export (§10.3).

Renders a summary cover sheet, then appends every document attached to the case — in step order
— into one PDF for leadership. Reuses the same LibreOffice path as the letters, so there is one
RTL-PDF pipeline to maintain, not several.

Inputs are always PDFs: the office scans to PDF, and the scan-capture feature (It.6) converts
camera images to PDF before upload. A file that is missing or unreadable therefore means
something is genuinely wrong, and the export **fails loudly** rather than quietly producing an
incomplete compilation that looks authoritative.
"""

import tempfile
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from pypdf import PdfReader, PdfWriter

from common.models import ActivityLog
from processes.constants import LAST_STEP
from common.services import record_activity

from processes.models import Process

from catalog.document_types import COMPILED_CASE, ELIGIBILITY_LETTER, IDENTITY_TYPE_CODES

from .idsheet import sheets_as_pdf
from .models import Document, DocumentTemplate, GenerationJob
from .rendering import RenderError
from .services import create_document, supersede_generated_documents
from .summary import case_summary_context

# The compiled export is Step-5 output and carries its own controlled type (§6.7), declared with
# the rest of the vocabulary in `catalog.document_types`. Re-exported under the name this module
# and its callers already use.
COMPILED_DOC_TYPE = COMPILED_CASE


# Never merged into the compiled export. The previous compilation, or each run would nest the
# last one inside the next and the file would grow without bound — and the Step-1 letter, which
# the office does not want in the compilation at all (UC-075). Nothing files a letter any more,
# but cases created before that change still carry one, and they must compile the same way.
EXCLUDED_FROM_COMPILATION = frozenset({COMPILED_CASE, ELIGIBILITY_LETTER})


def documents_in_step_order(process) -> list[Document]:
    """Every live document on the case that belongs in the compilation, in paper order: step 1 → 5."""
    return sorted(
        (
            document
            for document in process.documents.all()
            if document.document_type not in EXCLUDED_FROM_COMPILATION
        ),
        key=lambda d: (d.step_number, d.id),
    )


def _assert_readable(documents: list[Document]) -> None:
    """Every attachment must be present and parseable before any of it is merged.

    Checked up front rather than as each is added: a partial compilation must never look like a
    success (§10.3), and the identity cards are now composed before the rest of the file is
    walked, so a fault in a later document would otherwise surface halfway through.
    """
    root = Path(settings.DOCUMENTS_ROOT)
    for document in documents:
        path = root / document.file_path
        if not path.is_file():
            raise RenderError(
                f"Document #{document.id} ({document.display_filename}) is missing from the "
                f"document store, so the compiled case would be incomplete."
            )
        try:
            PdfReader(str(path)).pages[0]
        except Exception as exc:
            raise RenderError(
                f"Document #{document.id} ({document.display_filename}) could not be read as a "
                f"PDF: {exc}"
            ) from exc


def merge_pdfs(summary: bytes, documents: list[Document]) -> bytes:
    """Cover sheet, then the identity cards four to a page, then every other attachment.

    The cards are pulled out of the page flow and composed onto shared sheets (UC-081): each is
    scanned onto a full page, so four of them cost four near-empty pages in a file the office
    already found too long. They stay first, where the paper file keeps them.
    """
    writer = PdfWriter()
    for page in PdfReader(BytesIO(summary)).pages:
        writer.add_page(page)

    # Client card first, then the spouse's — the office reads the sheet as a row each, and filing
    # the spouse's scan before the beneficiary's would otherwise put it on the top row.
    cards = sorted(
        (d for d in documents if d.document_type in IDENTITY_TYPE_CODES),
        key=lambda d: (IDENTITY_TYPE_CODES.index(d.document_type), d.id),
    )
    # Read every attachment first — a card that cannot be read must fail the export just as loudly
    # as any other paper, and composing the sheet would otherwise quietly skip it.
    _assert_readable(documents)
    for page in PdfReader(BytesIO(sheets_as_pdf(cards))).pages if cards else []:
        writer.add_page(page)

    root = Path(settings.DOCUMENTS_ROOT)
    for document in documents:
        if document.document_type in IDENTITY_TYPE_CODES:
            continue  # already on the card sheets above
        for page in PdfReader(str(root / document.file_path)).pages:
            writer.add_page(page)

    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def run_compile_case_job(job_id: int) -> None:
    """Render the summary, merge the case, and attach the result to the process."""
    from .generation import render_to_pdf

    job = (
        GenerationJob.objects.select_related(
            "process__client", "process__category", "process__assigned_lawyer", "template"
        )
        # The summary walks all three collections; without this each is a separate round trip.
        .prefetch_related("process__steps", "process__documents", "process__institute_entries")
        .get(pk=job_id)
    )
    job.status = GenerationJob.Status.RUNNING
    job.save(update_fields=["status", "updated_at"])

    try:
        process = job.process
        attachments = documents_in_step_order(process)

        with tempfile.TemporaryDirectory(prefix="compile-") as work:
            summary = render_to_pdf(
                job.template, case_summary_context(process, attachments), Path(work)
            )
        merged = merge_pdfs(summary, attachments)

        with transaction.atomic():
            # Lock the case for the supersede-then-create window. Two computers compiling the
            # same case at once would otherwise interleave and both leave a live export (§12
            # concurrent edits) — the second waits here and supersedes the first's output.
            Process.objects.select_for_update().get(pk=process.pk)
            # A recompiled case supersedes the last one — row soft-deleted, audited, and its PDF
            # removed from disk. A compiled export is the largest file the app writes (every paper
            # on the case, merged), so keeping superseded copies grew the store fastest of all.
            supersede_generated_documents(
                process=process,
                document_type=COMPILED_DOC_TYPE,
                actor=job.requested_by,
                job_id=job.id,
            )
            document = create_document(
                process=process,
                step_number=LAST_STEP,
                document_type=COMPILED_DOC_TYPE,
                input_source=Document.InputSource.SYSTEM_GENERATED,
                content=merged,
                actor=job.requested_by,
            )
            job.document = document
            job.status = GenerationJob.Status.DONE
            job.save(update_fields=["document", "status", "updated_at"])
    except Exception as exc:  # a partial compilation must never look like a success
        job.status = GenerationJob.Status.FAILED
        job.error = str(exc)[:2000]
        job.save(update_fields=["status", "error", "updated_at"])
        raise


def start_compile_case_job(*, process, actor, template_id=None, request=None) -> GenerationJob:
    """Queue the compiled export for a process."""
    from .generation import _template_or_400
    from .tasks import compile_case

    template = _template_or_400(DocumentTemplate.TemplateType.CASE_SUMMARY, template_id)
    job = GenerationJob.objects.create(
        kind=GenerationJob.Kind.COMPILED_CASE,
        template=template,
        process=process,
        requested_by=actor,
    )
    # The compiled file gathers every document on a case into one export — the request is what
    # must be traceable, whether or not the merge later succeeds (§11).
    record_activity(
        actor=actor,
        action=ActivityLog.Action.GENERATE,
        entity_type="GenerationJob",
        entity_id=job.id,
        after={"kind": job.kind, "template_id": job.template_id, "process_id": process.id},
        request=request,
    )
    # on_commit: the worker must never look up a job row this transaction has not committed yet.
    transaction.on_commit(lambda: compile_case.delay(job.id))
    return job
