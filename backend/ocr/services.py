"""Write-side OCR rules and the sole place OCR writes audit (§6.5, §11, §14.2)."""

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from catalog.document_types import IDENTITY_TYPE_CODES, SPOUSE_ID
from clients.models import Client
from common.locking import check_version
from common.models import ActivityLog
from common.services import record_activity
from documents.models import Document

from .models import OcrRun

# The client fields a card can fill. Anything outside this set is ignored, so a future change to
# the draft shape can never quietly start writing to a column nobody reviewed.
CLIENT_FIELDS = ("pid", "full_name", "mother_full_name", "date_of_birth")
# `SpouseID` fills the spouse columns instead of the client's own.
SPOUSE_FIELD_MAP = {
    "full_name": "spouse_name",
    "mother_full_name": "spouse_mother_full_name",
    "date_of_birth": "spouse_date_of_birth",
}


def start_ocr(*, document: Document, actor, request=None) -> OcrRun:
    """Queue a reading of an identity document."""
    from .tasks import run_ocr

    if document.document_type not in IDENTITY_TYPE_CODES:
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
        run.error = _safe_error(exc)
        run.save(update_fields=["status", "error", "updated_at"])
        document.ocr_status = Document.OcrStatus.FAILED
        document.save(update_fields=["ocr_status"])
        raise
    return run


def _safe_error(exc: Exception) -> str:
    """The reason, without the absolute store path — this string is shown in the browser."""
    reason = f"{type(exc).__name__}: {exc}"
    return reason.replace(str(settings.DOCUMENTS_ROOT), "<documents>")[:2000]


def _target_field(source_field: str, *, is_spouse: bool) -> str | None:
    if not is_spouse:
        return source_field
    # A spouse's own PID is not stored — the client's PID is the identity key (§3.7).
    return SPOUSE_FIELD_MAP.get(source_field)


@transaction.atomic
def verify_ocr(
    *, run: OcrRun, values: dict, actor, request=None, client_version=None
) -> OcrRun:
    """Accept the (possibly corrected) values and write them to the client.

    `values` is what the human confirmed on screen, not what the engine proposed — the two differ
    whenever a field was corrected, and the corrected version is the one that counts. The draft is
    kept as-is so the trail records what OCR actually said versus what was accepted.
    """
    # Lock the run: the "already verified" guard below is a read-then-write, so two clicks (or
    # the two office computers) could otherwise both pass it and write the client twice.
    run = (
        OcrRun.objects.select_for_update()
        .select_related("document__process__client")
        .get(pk=run.pk)
    )
    if run.status != OcrRun.Status.DONE:
        raise ValidationError({"run": "This reading has not finished."})
    if run.verified_at:
        raise ValidationError({"run": "This reading has already been verified."})

    document = run.document
    is_spouse = document.document_type == SPOUSE_ID
    client = document.process.client
    # Same optimistic lock as every other write to this record (§4.1) — the verify screen and the
    # client details panel edit the same columns, so the loser of a race must get a 409, not win.
    check_version(client, client_version)

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
        _assert_pid_is_free(client, after)
        client.version += 1
        # Only the confirmed columns: a full save() would also write back everything the verify
        # screen never loaded, silently undoing a concurrent edit elsewhere on the record.
        client.save(update_fields=[*after, "version", "updated_at"])

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


def _assert_pid_is_free(client, after: dict) -> None:
    """Reject a card number another living client already holds — before the DB does.

    `ix_client_pid_active` would raise an IntegrityError here, which surfaces as an HTTP 500 and
    tells the lawyer nothing. A misread digit in a 12-digit card number is the likeliest OCR
    error there is, and it lands on the "no land twice" key, so the message has to name the
    conflict the way the duplicate-check dialog does (§3.7, §5.7).
    """
    pid = after.get("pid")
    if not pid:
        return
    # `Client.objects` hides soft-deleted rows — exactly the condition the partial index carries.
    conflict = Client.objects.filter(pid=pid).exclude(pk=client.pk).first()
    if conflict:
        raise ValidationError(
            {
                "pid": f"Card number {pid} already belongs to {conflict.full_name}. "
                f"Check the reading against the card."
            }
        )


def _corrected_fields(run: OcrRun, values: dict) -> list[str]:
    proposed = (run.draft or {}).get("fields", {})
    return sorted(
        name
        for name, value in values.items()
        if name in proposed and str(proposed[name].get("value", "")) != str(value or "")
    )
