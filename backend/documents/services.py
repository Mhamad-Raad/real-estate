"""Write-side rules for documents — validate the PDF, write to the store, audit (§4.4, §6.7)."""

from django.conf import settings
from django.db import transaction
from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError

from common.models import ActivityLog
from common.services import record_activity

from . import filestore
from .models import Document


class PayloadTooLarge(APIException):
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    default_detail = "The uploaded file is too large."
    default_code = "file_too_large"


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
    """Validate a PDF (magic bytes + size), write it under the deterministic path, and create the
    audited row. The file is written first; if the DB row fails, the orphan file is removed."""
    if len(content) > settings.MAX_UPLOAD_BYTES:
        raise PayloadTooLarge()
    if not filestore.looks_like_pdf(content):
        raise ValidationError({"file": "File is not a valid PDF."})

    client = process.client
    category_code = process.category.code if process.category_id else "NA"
    sid = filestore.short_id()
    display = filestore.compose_display_name(
        category_code=category_code,
        institute=filestore.institute_label(institute_entry),
        person_name=client.full_name,
        document_type=document_type,
        sid=sid,
    )
    rel = filestore.relative_path(
        category_code=category_code,
        client_id=client.id,
        pid=client.pid,
        display_filename=display,
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
