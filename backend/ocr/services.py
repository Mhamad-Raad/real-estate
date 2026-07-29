"""Write-side card-scan rules and the sole place OCR writes audit (§6.5, §6.7, §11, §14.2).

The flow this implements, end to end:

    photograph the card  →  staged PDF + OCR draft  →  human checks it side by side
                         →  confirm  →  client created, card filed, everything audited

Nothing is written to the domain until that confirmation. The reading is a *proposal*: it can be
edited freely, it can be thrown away entirely in favour of manual entry, and accepting it never
freezes anything — every field stays editable afterwards through the normal audited edit path.
"""

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from catalog.document_types import IDENTITY_TYPE_CODES, SPOUSE_ID
from clients.models import Client
from clients.services import create_client
from common.locking import check_version
from common.models import ActivityLog
from common.services import record_activity
from documents import filestore
from documents.services import PayloadTooLarge, file_staged_document
from processes.services import create_process, recompute_client_steps

from .models import CardScan

# The client fields a card can fill. Anything outside this set is ignored, so a future change to
# the draft shape can never quietly start writing to a column nobody reviewed.
CLIENT_FIELDS = ("pid", "full_name", "mother_full_name", "date_of_birth")
# `SpouseID` fills the spouse columns instead of the client's own.
SPOUSE_FIELD_MAP = {
    "full_name": "spouse_name",
    "mother_full_name": "spouse_mother_full_name",
    "date_of_birth": "spouse_date_of_birth",
}
# Identity papers belong to Step 1 (§3.6).
IDENTITY_STEP = 1


def stage_scan(*, content: bytes, document_type: str, actor, original_filename="", request=None):
    """Accept a photographed card, write it to staging, and queue the reading.

    The file is written to disk before anything else: a photograph that exists only in a browser
    tab is one closed window away from making the lawyer fetch the citizen back (§2.5).
    """
    from .tasks import read_card_scan

    if document_type not in IDENTITY_TYPE_CODES:
        raise ValidationError({"document_type": "Only identity cards can be read."})
    if len(content) > settings.MAX_UPLOAD_BYTES:
        raise PayloadTooLarge()

    # A photographed ID arrives as a JPEG; convert on arrival so the store holds PDFs only and
    # every downstream reader (review pane, OCR, compile) has exactly one format to handle.
    if filestore.looks_like_image(content):
        try:
            content = filestore.image_to_pdf(content)
        except Exception as exc:
            # Truncated, mislabelled or hostile image data is a bad upload, not a server fault.
            raise ValidationError({"file": "File is not a readable image."}) from exc
    if not filestore.is_readable_pdf(content):
        raise ValidationError({"file": "File is not a readable PDF."})

    rel = filestore.staging_path(filestore.short_id())
    filestore.write_pdf(rel, content)
    scan = CardScan.objects.create(
        document_type=document_type,
        file_path=str(rel),
        original_filename=original_filename[:255],
        sha256=filestore.sha256_hex(content),
        size_bytes=len(content),
        uploaded_by=actor,
    )
    record_activity(
        actor=actor,
        action=ActivityLog.Action.CREATE,
        entity_type="CardScan",
        entity_id=scan.id,
        after={"document_type": document_type, "size_bytes": scan.size_bytes},
        request=request,
    )
    # on_commit: the worker must never look up a scan row this transaction has not committed yet.
    transaction.on_commit(lambda: read_card_scan.delay(scan.id))
    return scan


def read_scan(scan_id: int) -> CardScan:
    """Read the staged card and store the draft. Runs inside the worker."""
    from .reader import read_card

    scan = CardScan.objects.get(pk=scan_id)
    scan.status = CardScan.Status.RUNNING
    scan.save(update_fields=["status", "updated_at"])

    try:
        # One draft per scan: a re-read replaces it. What the engine proposed versus what the
        # human accepted is preserved permanently in the audit log, not in a pile of drafts.
        scan.draft = read_card(settings.DOCUMENTS_ROOT / scan.file_path).as_dict()
        scan.status = CardScan.Status.DONE
        scan.save(update_fields=["draft", "status", "updated_at"])
    except Exception as exc:  # a failed read must never look like an empty-but-valid draft
        scan.status = CardScan.Status.FAILED
        scan.error = _safe_error(exc)
        scan.save(update_fields=["status", "error", "updated_at"])
        raise
    return scan


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
def confirm_scan(
    *,
    scan: CardScan,
    values: dict,
    actor,
    assigned_lawyer=None,
    category=None,
    client=None,
    client_version=None,
    request=None,
) -> CardScan:
    """Turn a checked reading into real records, in one transaction (§6.7).

    Either the card creates the person — client, case and filed document together — or it updates
    someone already on file (a spouse card, or a replacement scan). Only here does the document
    reach `<CATEGORY>/<client_id>_<pid>/`: the folder is keyed by the PID and the name by the
    person, and both are what the lawyer has just confirmed.

    `values` is what the human confirmed on screen, not what the engine proposed — the two differ
    whenever a field was corrected, and the corrected version is the one that counts. A reading
    the engine failed at is no obstacle: the lawyer types the fields and confirms them the same way.
    """
    # Lock the scan: the "already confirmed" guard below is a read-then-write, so two clicks (or
    # the two office computers) could otherwise both pass it and file the card twice.
    scan = CardScan.objects.select_for_update().get(pk=scan.pk)
    if scan.is_confirmed:
        raise ValidationError({"scan": "This card has already been confirmed."})
    if not scan.file_path:
        raise ValidationError({"scan": "This scan has no file to file."})

    is_spouse = scan.document_type == SPOUSE_ID
    created_client = client is None
    if created_client and is_spouse:
        raise ValidationError({"client": "A spouse card belongs to a client that already exists."})

    if created_client:
        client, process = _create_from_card(
            values=values, actor=actor, assigned_lawyer=assigned_lawyer,
            category=category, request=request,
        )
        before, after = {}, {k: str(v) for k, v in values.items() if v not in (None, "")}
    else:
        # Same optimistic lock as every other write to this record (§4.1) — the review screen and
        # the client details panel edit the same columns, so the loser of a race gets a 409.
        check_version(client, client_version)
        process = _active_process(client)
        before, after = _apply_to_client(client, values, is_spouse=is_spouse)
        if after:
            _assert_pid_is_free(client, after)
            client.version += 1
            # Only the confirmed columns: a full save() would also write back everything the
            # review screen never loaded, silently undoing a concurrent edit on the record.
            client.save(update_fields=[*after, "version", "updated_at"])

    document = file_staged_document(
        staged_path=scan.file_path,
        process=process,
        step_number=IDENTITY_STEP,
        document_type=scan.document_type,
        actor=actor,
        sha256=scan.sha256,
        size_bytes=scan.size_bytes,
        original_filename=scan.original_filename,
        request=request,
    )

    scan.document = document
    scan.file_path = ""  # it lives in the person's folder now; the document row owns the pointer
    scan.confirmed_at = timezone.now()
    scan.confirmed_by = actor
    scan.save(update_fields=["document", "file_path", "confirmed_at", "confirmed_by", "updated_at"])

    record_activity(
        actor=actor,
        action=ActivityLog.Action.VERIFY,
        entity_type="Client",
        entity_id=client.id,
        before=before,
        # `corrected` marks the fields the human changed from what the engine proposed — the
        # signal for judging how well OCR is doing on real cards, kept for good in the audit log.
        after={
            **after,
            "card_scan_id": scan.id,
            "document_id": document.id,
            "corrected": _corrected_fields(scan, values),
        },
        request=request,
    )
    # A confirmed identity paper can complete Step 1, so the stored status must be re-derived.
    recompute_client_steps(client)
    return scan


def _create_from_card(*, values: dict, actor, assigned_lawyer, category, request):
    """Create the person and their case from the confirmed reading."""
    if assigned_lawyer is None:
        raise ValidationError({"assigned_lawyer": "A new case needs an assigned lawyer."})
    missing = [name for name in CLIENT_FIELDS if not values.get(name)]
    if missing:
        raise ValidationError(
            {name: "Required to create a client from a card." for name in missing}
        )
    _assert_pid_is_free(None, {"pid": values["pid"]})
    client = create_client(
        data={name: values[name] for name in CLIENT_FIELDS}, actor=actor, request=request
    )
    process = create_process(
        client=client,
        assigned_lawyer=assigned_lawyer,
        category=category,
        actor=actor,
        request=request,
    )
    return client, process


def _active_process(client):
    process = (
        client.processes.exclude(overall_status="rejected").order_by("-created_at").first()
    )
    if process is None:
        raise ValidationError({"client": "This client has no active case to file the card on."})
    return process


def _apply_to_client(client, values: dict, *, is_spouse: bool) -> tuple[dict, dict]:
    """Copy the confirmed values onto the client, reporting what actually changed."""
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
    return before, after


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
    candidates = Client.objects.filter(pid=pid)
    if client is not None:
        candidates = candidates.exclude(pk=client.pk)
    conflict = candidates.first()
    if conflict:
        raise ValidationError(
            {
                "pid": f"Card number {pid} already belongs to {conflict.full_name}. "
                f"Check the reading against the card."
            }
        )


def _corrected_fields(scan: CardScan, values: dict) -> list[str]:
    proposed = (scan.draft or {}).get("fields", {})
    return sorted(
        name
        for name, value in values.items()
        if name in proposed and str(proposed[name].get("value", "")) != str(value or "")
    )
