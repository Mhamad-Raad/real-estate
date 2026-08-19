"""Write-side rules for documents — validate the PDF, write to the store, audit (§4.4, §6.7)."""

import io
from pathlib import Path

from django.conf import settings
from django.db import transaction
from rest_framework import status
from docxtpl import DocxTemplate
from rest_framework.exceptions import APIException, ValidationError

from catalog.document_types import SPOUSE_ID, slot_capacity
from common.models import ActivityLog
from common.services import record_activity
from common.validators import SLOT_FILES_FULL, SLOT_SIDES_FULL

from . import filestore
from .models import Document, DocumentTemplate
from .selectors import slot_usage


class PayloadTooLarge(APIException):
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    default_detail = "The uploaded file is too large."
    default_code = "file_too_large"


def assert_slot_has_room(
    *, process, step_number: int, document_type: str, pages: int, institute_entry=None
) -> None:
    """Refuse a file the slot has no room for (UC-085).

    An identity card has exactly two sides and every other paper is filed once — the office was
    able to keep adding to a full slot, so a card ended up with four sides after a re-scan and the
    count could only be capped for display. Capacity is `expected_parts` (§6.7), so the rule and
    the "2 of 2 sides" hint can never disagree.

    Enforced here rather than in the serializer because both upload paths must obey it: the import
    button and the confirmed card scan, which files its document straight from staging. Making
    room is a delete — the rule counts live rows only.
    """
    limit, by_pages = slot_capacity(document_type)
    filed = slot_usage(
        process_id=process.id,
        step_number=step_number,
        document_type=document_type,
        institute_entry_id=institute_entry.id if institute_entry else None,
        by_pages=by_pages,
    )
    # A card's pages are its sides, so a two-page scan fills the slot on its own; anything else
    # counts as the one paper it is, however many pages that paper happens to have.
    if filed + (pages if by_pages else 1) > limit:
        raise ValidationError({"file": [SLOT_SIDES_FULL if by_pages else SLOT_FILES_FULL]})


def read_upload(upload, *, limit: int | None = None) -> bytes:
    """Read an uploaded file into memory, refusing an oversized one **before** the read.

    Django spools anything past `FILE_UPLOAD_MAX_MEMORY_SIZE` to a temp file, so `.read()` on a
    huge upload pulls the whole thing into the worker's RAM and only then meets the cap. Asking
    the upload for its size first costs nothing and keeps the 413 cheap (It.8).
    """
    limit = settings.MAX_UPLOAD_BYTES if limit is None else limit
    if getattr(upload, "size", 0) > limit:
        raise PayloadTooLarge()
    return upload.read()


def subject_name(client, document_type: str) -> str:
    """Whose document this is. A spouse's ID card is the *spouse's* paper even though it lives in
    the beneficiary's folder, so naming it after the beneficiary would misdescribe it (§6.7)."""
    if document_type == SPOUSE_ID and client.spouse_name:
        return client.spouse_name
    return client.full_name


def normalise_to_pdf(content: bytes, *, field: str = "file") -> bytes:
    """One uploaded file, validated and returned as PDF bytes (§6.7).

    A photographed page arrives as JPEG/PNG/TIFF; converting on arrival keeps the store PDF-only
    so every downstream reader (preview, OCR, compile) handles exactly one format. Both failure
    modes are bad *input* — truncated, mislabelled or hostile bytes, including a decompression
    bomb — so they raise `ValidationError` and read as 400, never as a 500 from inside a decoder.
    `field` names the offending upload, because a card scan posts two of them (front and back).
    """
    if filestore.looks_like_image(content):
        try:
            return filestore.image_to_pdf(content)
        except Exception as exc:
            raise ValidationError({field: "File is not a readable image."}) from exc
    if not filestore.is_readable_pdf(content):
        raise ValidationError({field: "File is not a readable PDF."})
    return content


def compose_names(*, process, document_type: str, institute_entry=None) -> tuple[str, str, "Path"]:
    """The download name, the label and the case folder for a document on this process (§6.7).

    Everything about where a document belongs **except which file inside the folder** — that last
    part differs between filing a new document (claim the next free number) and re-filing an
    existing one (keep the number it already has), so it is the caller's to decide.

    All of it needs the person: the category and PID key the folder, and the subject names the
    file. That is why a scanned ID is only filed once its reading has been confirmed — before
    that, the very fields this composition needs are still what the card is proposing.
    """
    client = process.client
    category_code = process.category.code if process.category_id else "NA"
    # One label serves both names — the issuing body when there is one, else the paper's own name.
    label = filestore.document_label(document_type, institute_entry)
    display = filestore.compose_display_name(
        unique_code=process.unique_code,
        category_code=category_code,
        person_name=subject_name(client, document_type),
        label=label,
    )
    directory = filestore.case_directory(
        category_code=category_code, unique_code=process.unique_code, pid=client.pid
    )
    return display, label, directory


def compose_location(*, process, document_type: str, institute_entry=None) -> tuple[str, "Path"]:
    """The download name and a **freshly claimed** store path — for a document being filed now.

    The name is claimed on disk as it is composed (UC-097), so the caller's write, or the move
    deferred to commit, lands somewhere no concurrent filing can have taken.
    """
    display, label, directory = compose_names(
        process=process, document_type=document_type, institute_entry=institute_entry
    )
    return display, filestore.reserve_stored_name(directory=directory, label=label)


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
    # Counted from the staged file, while it is still where it was written — the move below only
    # happens on commit. This is the path that produces a two-page card from two scans (UC-083).
    staged = Path(settings.DOCUMENTS_ROOT) / staged_path
    pages = filestore.count_pages(staged.read_bytes()) if staged.is_file() else 0
    # A re-scan of a card already on file is what filled a slot past its two sides — the lawyer
    # deletes the old one first, exactly as they would to replace an imported PDF.
    assert_slot_has_room(
        process=process, step_number=step_number, document_type=document_type, pages=pages
    )
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
            page_count=pages,
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


def supersede_generated_documents(*, process, document_type: str, actor, job_id=None) -> int:
    """Retire the previous copies of a **regenerated** document, file and all (§6.6, §10.3).

    Regenerating the eligibility letter or recompiling the case replaces the previous output. The
    old row is soft-deleted and audited as always — but its **PDF is also removed from disk**,
    which is the difference from every other delete in this app.

    Why that is safe here and nowhere else: a superseded generated file has no way back. The
    restore desk (UC-063) can bring a *user-deleted* document row back to life, and its file must
    therefore survive; a superseded one is never restored — pressing Generate again produces a
    fresh row and a fresh file. Keeping the old PDF bought nothing and grew the store on every
    press, which is what the office noticed.

    **What is kept:** the `ActivityLog` row, so the trail still shows that a letter existed, who
    generated it, when it was replaced and by which job. What is lost is the ability to reprint the
    exact earlier PDF — the office's call (2026-08-11), taken to stop the store growing without
    bound. Never call this for a document a person deleted.
    """
    from django.utils import timezone

    root = Path(settings.DOCUMENTS_ROOT)
    superseded = 0
    for old in Document.objects.filter(process=process, document_type=document_type):
        old.is_deleted = True
        old.deleted_at = timezone.now()
        old.deleted_by = actor
        old.version += 1
        old.save(update_fields=["is_deleted", "deleted_at", "deleted_by", "version"])
        record_activity(
            actor=actor,
            action=ActivityLog.Action.DELETE,
            entity_type="Document",
            entity_id=old.pk,
            before={
                "display_filename": old.display_filename,
                "superseded_by_job": job_id,
                "file_removed": True,
            },
        )
        # After the audit row, and tolerant of an already-missing file: the store is a bind mount
        # the office can reach by hand (§2.5), so a file may legitimately be gone already.
        (root / old.file_path).unlink(missing_ok=True)
        superseded += 1
    return superseded


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

    content = normalise_to_pdf(content)
    pages = filestore.count_pages(content)
    # Only what a person files: the compiled export and the letters are system output that
    # supersedes its own previous copy, so a capacity meant for uploads does not apply to them.
    if not generated:
        assert_slot_has_room(
            process=process,
            step_number=step_number,
            document_type=document_type,
            pages=pages,
            institute_entry=institute_entry,
        )

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
                page_count=pages,
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
    """Validate and store a template file, making it the active one for its type.

    A letter is a `.docx` the system later fills in; a blank form (§6.6) is the PDF the office
    prints as-is. Either way the file is parsed here, so a corrupt one fails at install rather
    than in front of the office. The previous active template is deactivated rather than deleted —
    a regenerated letter must still be traceable to the exact file that produced the earlier one.
    """
    content = upload.read()
    if len(content) > settings.MAX_UPLOAD_BYTES:
        raise PayloadTooLarge()
    if template_type in DocumentTemplate.BLANK_FORM_TYPES:
        if not filestore.is_readable_pdf(content):
            raise ValidationError({"file": "File is not a readable PDF."})
        suffix = ".pdf"
    else:
        if not filestore.looks_like_docx(content):
            raise ValidationError({"file": "File is not a .docx document."})
        # Opening it here means a corrupt template fails at upload, not mid-generation.
        try:
            DocxTemplate(io.BytesIO(content)).get_undeclared_template_variables()
        except Exception as exc:
            raise ValidationError({"file": f"File is not a readable Word template: {exc}"}) from exc
        suffix = ".docx"

    rel = filestore.write_template(
        template_type=template_type, name=name, content=content, suffix=suffix
    )
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
