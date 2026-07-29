"""Write-side rules for documents — validate the PDF, write to the store, audit (§4.4, §6.7)."""

import io
from pathlib import Path

from django.conf import settings
from django.db import transaction
from rest_framework import status
from docxtpl import DocxTemplate
from rest_framework.exceptions import APIException, ValidationError

from catalog.document_types import SPOUSE_ID
from common.models import ActivityLog
from common.services import record_activity

from . import filestore
from .models import Document, DocumentTemplate


class PayloadTooLarge(APIException):
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    default_detail = "The uploaded file is too large."
    default_code = "file_too_large"


def subject_name(client, document_type: str) -> str:
    """Whose document this is. A spouse's ID card is the *spouse's* paper even though it lives in
    the beneficiary's folder, so naming it after the beneficiary would misdescribe it (§6.7)."""
    if document_type == SPOUSE_ID and client.spouse_name:
        return client.spouse_name
    return client.full_name


def compose_location(*, process, document_type: str, institute_entry=None) -> tuple[str, "Path"]:
    """The download name and the store path for a document on this process (§6.7).

    Both need the person: the category and PID key the folder, and the subject names the file.
    That is why a scanned ID is only filed once its reading has been confirmed — before that, the
    very fields this composition needs are still what the card is proposing.
    """
    client = process.client
    category_code = process.category.code if process.category_id else "NA"
    sid = filestore.short_id()
    institute = filestore.institute_label(institute_entry)
    display = filestore.compose_display_name(
        category_code=category_code,
        institute=institute,
        person_name=subject_name(client, document_type),
        document_type=document_type,
        sid=sid,
    )
    rel = filestore.relative_path(
        category_code=category_code,
        pid=client.pid,
        stored_filename=filestore.compose_stored_name(
            institute=institute, document_type=document_type, sid=sid
        ),
    )
    return display, rel


def file_staged_document(
    *,
    staged_path: str,
    process,
    step_number: int,
    document_type: str,
    actor,
    sha256: str,
    size_bytes: int,
    original_filename: str = "",
    request=None,
) -> Document:
    """Move an already-staged scan into the person's folder and create its verified row (§6.7).

    The bytes were validated when they were staged, so this only relocates them — the file is
    moved, not rewritten, so the recorded sha256 keeps describing exactly what was uploaded.

    **The move happens on commit, not now.** A filesystem move cannot be rolled back with the
    transaction, and this one relocates the *only* copy of a citizen's ID: moving it inline meant
    that any later failure in the caller left the file in the person's folder while the database
    forgot it ever moved — the scan then pointed at a path that no longer existed and could
    neither be previewed nor re-confirmed. Deferring to `on_commit` makes the failure mode
    "nothing happened" instead of "the scan is gone".
    """
    display, rel = compose_location(process=process, document_type=document_type)
    with transaction.atomic():
        document = Document.objects.create(
            process=process,
            step_number=step_number,
            document_type=document_type,
            input_source=Document.InputSource.SCANNED,
            file_path=str(rel),
            display_filename=display,
            sha256=sha256,
            original_filename=original_filename[:255],
            size_bytes=size_bytes,
            uploaded_by=actor,
            ocr_status=Document.OcrStatus.DONE,
            # Filed only because a human confirmed the reading — that is what this row is.
            verification_status=Document.VerificationStatus.VERIFIED,
        )
        record_activity(
            actor=actor,
            action=ActivityLog.Action.CREATE,
            entity_type="Document",
            entity_id=document.id,
            after={"display_filename": display, "process_id": process.id, "step": step_number},
            request=request,
        )
        # Only once every row is safely committed does the file actually move.
        transaction.on_commit(
            lambda: filestore.move_into_place(source=Path(staged_path), rel_path=rel)
        )
    return document


def create_document(
    *,
    process,
    step_number: int,
    document_type: str,
    input_source: str,
    content: bytes,
    actor,
    institute_entry=None,
    original_filename: str = "",
    request=None,
) -> Document:
    """Validate the upload (size, then a real parse — converting an image to PDF first), write it
    under the deterministic path, and create the audited row. The file is written first; if the DB
    row fails, the orphan file is removed."""
    # The upload cap bounds what a *user* may send. A system-generated file (the compiled case,
    # §10.3) merges documents that were each already accepted, so holding it to the same limit
    # would reject a legitimate export of a large case; it gets the runaway-merge bound instead.
    generated = input_source == Document.InputSource.SYSTEM_GENERATED
    limit = settings.MAX_GENERATED_BYTES if generated else settings.MAX_UPLOAD_BYTES
    if len(content) > limit:
        raise PayloadTooLarge()

    # A photographed ID arrives as a JPEG; convert here so the store holds PDFs only and every
    # downstream reader (compile, OCR, preview) has exactly one format to handle.
    if filestore.looks_like_image(content):
        try:
            content = filestore.image_to_pdf(content)
        except Exception as exc:
            # Truncated, mislabelled or hostile image data (a decompression bomb raises here too)
            # is a bad upload, not a server fault — it must read as 400, like every other upload.
            raise ValidationError({"file": "File is not a readable image."}) from exc
    if not filestore.is_readable_pdf(content):
        raise ValidationError({"file": "File is not a readable PDF."})

    display, rel = compose_location(
        process=process, document_type=document_type, institute_entry=institute_entry
    )
    dest = filestore.write_pdf(rel, content)
    try:
        with transaction.atomic():
            document = Document.objects.create(
                process=process,
                step_number=step_number,
                document_type=document_type,
                institute_entry=institute_entry,
                input_source=input_source,
                file_path=str(rel),
                display_filename=display,
                sha256=filestore.sha256_hex(content),
                original_filename=original_filename[:255],
                size_bytes=len(content),
                uploaded_by=actor,
            )
            record_activity(
                actor=actor,
                action=ActivityLog.Action.CREATE,
                entity_type="Document",
                entity_id=document.id,
                after={"display_filename": display, "process_id": process.id, "step": step_number},
                request=request,
            )
    except Exception:
        dest.unlink(missing_ok=True)  # don't leave an orphan file if the row didn't commit
        raise
    return document


def create_template(*, template_type: str, name: str, upload, actor, request=None):
    """Validate and store a `.docx` letter template, making it the active one for its type.

    The previous active template is deactivated rather than deleted — a regenerated letter must
    still be traceable to the exact file that produced the earlier one (§6.6).
    """
    content = upload.read()
    if len(content) > settings.MAX_UPLOAD_BYTES:
        raise PayloadTooLarge()
    if not filestore.looks_like_docx(content):
        raise ValidationError({"file": "File is not a .docx document."})
    # Opening it here means a corrupt template fails at upload, not mid-generation.
    try:
        DocxTemplate(io.BytesIO(content)).get_undeclared_template_variables()
    except Exception as exc:
        raise ValidationError({"file": f"File is not a readable Word template: {exc}"}) from exc

    rel = filestore.write_template(template_type=template_type, name=name, content=content)
    try:
        with transaction.atomic():
            DocumentTemplate.objects.filter(
                template_type=template_type, is_active=True
            ).update(is_active=False)
            template = DocumentTemplate.objects.create(
                template_type=template_type,
                name=name,
                file_path=str(rel),
                original_filename=getattr(upload, "name", "")[:255],
                sha256=filestore.sha256_hex(content),
                size_bytes=len(content),
                uploaded_by=actor,
            )
            record_activity(
                actor=actor,
                action=ActivityLog.Action.CREATE,
                entity_type="DocumentTemplate",
                entity_id=template.id,
                after={"name": name, "template_type": template_type},
                request=request,
            )
    except Exception:
        (settings.LETTER_TEMPLATES_ROOT / rel).unlink(missing_ok=True)
        raise
    return template
