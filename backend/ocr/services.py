"""Write-side OCR rules and the sole place OCR writes audit (§6.5, §11, §14.2)."""

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from common.models import ActivityLog
from common.services import record_activity
from documents.models import Document

from .models import OcrRun

# The client fields a card can fill. Anything outside this set is ignored, so a future change to
# the draft shape can never quietly start writing to a column nobody reviewed.
CLIENT_FIELDS = ("pid", "full_name", "mother_full_name", "date_of_birth")
# Types worth reading: the two identity documents. Everything else is filed, not parsed.
READABLE_TYPES = ("ClientID", "SpouseID")
# `SpouseID` fills the spouse columns instead of the client's own.
SPOUSE_FIELD_MAP = {
    "full_name": "spouse_name",
    "mother_full_name": "spouse_mother_full_name",
    "date_of_birth": "spouse_date_of_birth",
}


def start_ocr(*, document: Document, actor, request=None) -> OcrRun:
    """Queue a reading of an identity document."""
    from .tasks import run_ocr

    if document.document_type not in READABLE_TYPES:
        raise ValidationError({"document": "Only identity documents can be read."})

    run = OcrRun.objects.create(document=document, requested_by=actor)
    document.ocr_status = Document.OcrStatus.PENDING
    document.save(update_fields=["ocr_status"])
    record_activity(
        actor=actor,
        action=ActivityLog.Action.GENERATE,
        entity_type="OcrRun",
        entity_id=run.id,
        after={"document_id": document.id, "document_type": document.document_type},
        request=request,
    )
    # on_commit: the worker must never look up a run row this transaction has not committed yet.
    transaction.on_commit(lambda: run_ocr.delay(run.id))
    return run


def execute_ocr(run_id: int) -> OcrRun:
    """Read the document and store the draft. Runs inside the worker."""
    from .reader import read_document

    run = OcrRun.objects.select_related("document").get(pk=run_id)
    run.status = OcrRun.Status.RUNNING
    run.save(update_fields=["status", "updated_at"])
    document = run.document

    try:
        run.draft = read_document(document).as_dict()
        run.status = OcrRun.Status.DONE
        run.save(update_fields=["draft", "status", "updated_at"])
        # Waiting on a person now — not "done" in the sense of finished (§6.5).
        document.ocr_status = Document.OcrStatus.DONE
        document.verification_status = Document.VerificationStatus.PENDING
        document.save(update_fields=["ocr_status", "verification_status"])
    except Exception as exc:  # a failed read must never look like an empty-but-valid draft
        run.status = OcrRun.Status.FAILED
        run.error = str(exc)[:2000]
        run.save(update_fields=["status", "error", "updated_at"])
        document.ocr_status = Document.OcrStatus.FAILED
        document.save(update_fields=["ocr_status"])
        raise
    return run


def _target_field(source_field: str, *, is_spouse: bool) -> str | None:
    if not is_spouse:
        return source_field
    # A spouse's own PID is not stored — the client's PID is the identity key (§3.7).
    return SPOUSE_FIELD_MAP.get(source_field)


@transaction.atomic
def verify_ocr(*, run: OcrRun, values: dict, actor, request=None) -> OcrRun:
    """Accept the (possibly corrected) values and write them to the client.

    `values` is what the human confirmed on screen, not what the engine proposed — the two differ
    whenever a field was corrected, and the corrected version is the one that counts. The draft is
    kept as-is so the trail records what OCR actually said versus what was accepted.
    """
    if run.status != OcrRun.Status.DONE:
        raise ValidationError({"run": "This reading has not finished."})
    if run.verified_at:
        raise ValidationError({"run": "This reading has already been verified."})

    document = run.document
    is_spouse = document.document_type == "SpouseID"
    client = document.process.client

    before, after = {}, {}
    for source_field in CLIENT_FIELDS:
        if source_field not in values:
            continue
        target = _target_field(source_field, is_spouse=is_spouse)
        if target is None:
            continue
        new_value = values[source_field]
        if new_value in (None, ""):
            continue
        current = getattr(client, target)
        # Compare as text: a date field holds a `date` while the payload carries an ISO string.
        if str(current or "") == str(new_value):
            continue
        before[target] = str(current or "")
        after[target] = str(new_value)
        setattr(client, target, new_value)

    if after:
        client.version += 1
        client.save()

    run.verified_at = timezone.now()
    run.verified_by = actor
    run.save(update_fields=["verified_at", "verified_by", "updated_at"])
    document.verification_status = Document.VerificationStatus.VERIFIED
    document.save(update_fields=["verification_status"])

    record_activity(
        actor=actor,
        action=ActivityLog.Action.VERIFY,
        entity_type="Client",
        entity_id=client.id,
        before=before,
        # `corrected` marks the fields the human changed from what the engine proposed — the
        # signal for judging how well OCR is doing on real cards.
        after={**after, "ocr_run_id": run.id, "corrected": _corrected_fields(run, values)},
        request=request,
    )
    return run


def _corrected_fields(run: OcrRun, values: dict) -> list[str]:
    proposed = (run.draft or {}).get("fields", {})
    return sorted(
        name
        for name, value in values.items()
        if name in proposed and str(proposed[name].get("value", "")) != str(value or "")
    )
