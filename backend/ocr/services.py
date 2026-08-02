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
from clients.services import assert_pid_is_free
from common.locking import check_version
from common.models import ActivityLog
from common.services import record_activity
from documents import filestore
from documents.services import PayloadTooLarge, file_staged_document, normalise_to_pdf
from processes.services import intake_process, recompute_client_state

from .models import CardScan

# The client fields a card can fill. Anything outside this set is ignored, so a future change to
# the draft shape can never quietly start writing to a column nobody reviewed.
CLIENT_FIELDS = ("pid", "full_name", "mother_full_name", "date_of_birth")
# `SpouseID` fills the spouse columns instead of the client's own. The spouse's PID is stored
# too — not for the letter, which never prints it, but because a household may hold only one
# allocation and that rule needs the spouse to be identifiable (§3.7, §5.7).
SPOUSE_FIELD_MAP = {
    "full_name": "spouse_name",
    "mother_full_name": "spouse_mother_full_name",
    "date_of_birth": "spouse_date_of_birth",
    "pid": "spouse_pid",
}
# Identity papers belong to Step 1 (§3.6).
IDENTITY_STEP = 1


def stage_scan(
    *, content: bytes, document_type: str, actor, back=None, original_filename="", request=None
):
    """Accept a photographed card, write it to staging, and queue the reading.

    Both sides become **one** PDF — front on page 1, back on page 2. A card is a single document,
    so it gets a single row and a single file in the case folder; it also gives the reader both
    sides together, which is what makes the front↔MRZ cross-check possible (§6.2).

    The file is written to disk before anything else: a photograph that exists only in a browser
    tab is one closed window away from making the lawyer fetch the citizen back (§2.5).
    """
    from .tasks import read_card_scan

    if document_type not in IDENTITY_TYPE_CODES:
        raise ValidationError({"document_type": "Only identity cards can be read."})
    if len(content) + len(back or b"") > settings.MAX_UPLOAD_BYTES:
        raise PayloadTooLarge()

    content = normalise_to_pdf(content, field="front")
    if back:
        content = filestore.merge_pdfs([content, normalise_to_pdf(back, field="back")])

    rel = filestore.staging_path(filestore.short_id())
    dest = filestore.write_pdf(rel, content)
    try:
        with transaction.atomic():
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
    except Exception:
        # No row means no sweep can ever find this file again — remove it now (§6.3).
        dest.unlink(missing_ok=True)
        raise
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
    return SPOUSE_FIELD_MAP.get(source_field)


@transaction.atomic
def confirm_scan(
    *,
    scan: CardScan,
    values: dict,
    actor,
    assigned_lawyer=None,
    category=None,
    land_id="",
    land_address="",
    client=None,
    client_version=None,
    request=None,
) -> CardScan:
    """Turn a checked reading into real records, in one transaction (§6.7).

    Either the card creates the person — client, case and filed document together — or it updates
    someone already on file (a spouse card, or a replacement scan). Only here does the document
    reach `<CATEGORY>/<pid>/`: the folder is keyed by the PID and the download name by the
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
            category=category, land_id=land_id, land_address=land_address, request=request,
        )
        before, after = {}, {k: str(v) for k, v in values.items() if v not in (None, "")}
    else:
        # Same optimistic lock as every other write to this record (§4.1) — the review screen and
        # the client details panel edit the same columns, so the loser of a race gets a 409.
        check_version(client, client_version)
        process = active_process_for(client)
        before, after = _apply_to_client(client, values, is_spouse=is_spouse)
        if after:
            assert_pid_is_free(after.get('pid'), exclude=client)
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
    # A confirmed identity paper can complete Step 1, and a spouse card has just supplied the key
    # the household duplicate rule reads — both are server-derived and must be refreshed (§5.7).
    recompute_client_state(client)
    return scan


def _create_from_card(
    *, values: dict, actor, assigned_lawyer, category, land_id, land_address, request
):
    """Create the person and their case from the confirmed reading.

    Shares `intake_process` with the typed and find-existing paths of the Step-1 form, so all three
    ways of opening a case commit the same way and there is only one place that can get it wrong.
    """
    if assigned_lawyer is None:
        raise ValidationError({"assigned_lawyer": "A new case needs an assigned lawyer."})
    missing = [name for name in CLIENT_FIELDS if not values.get(name)]
    if missing:
        raise ValidationError(
            {name: "Required to create a client from a card." for name in missing}
        )
    assert_pid_is_free(values["pid"])

    data = {name: values[name] for name in CLIENT_FIELDS}
    data.update(_marital_details(values))
    process = intake_process(
        client_data=data,
        assigned_lawyer=assigned_lawyer,
        category=category,
        land_id=land_id,
        land_address=land_address,
        actor=actor,
        request=request,
    )
    return process.client, process


# The letter prints a spouse row of name / birth date / mother's name, and the DB check
# constraint demands all three together — the same set `ClientSerializer` enforces (§6.6).
SPOUSE_REQUIRED = ("spouse_name", "spouse_date_of_birth", "spouse_mother_full_name")


def _marital_details(values: dict) -> dict:
    """Marital status and, when married, the spouse block that must accompany it.

    Not on the card — the person creating the record says. Validated here rather than left to the
    DB constraint, which would surface as an unexplained 500 (§3.6, §6.6).
    """
    status = values.get("marital_status") or Client.MaritalStatus.SINGLE
    if status != Client.MaritalStatus.MARRIED:
        return {"marital_status": status}

    absent = [name for name in SPOUSE_REQUIRED if not values.get(name)]
    if absent:
        raise ValidationError(
            {name: "Required for a married beneficiary — the letter prints it." for name in absent}
        )
    details = {"marital_status": status, **{name: values[name] for name in SPOUSE_REQUIRED}}
    # Optional: the letter never prints it, it only feeds the household duplicate rule (§5.7).
    if values.get("spouse_pid"):
        details["spouse_pid"] = values["spouse_pid"]
    return details


def active_process_for(client):
    """The live case a card is filed onto. Public because the permission check needs the *same*
    case the write will target — testing "is this lawyer on any of their cases" would let someone
    assigned only to a rejected case file onto the live one (§4.2)."""
    from processes.models import Process

    process = (
        client.processes.exclude(overall_status=Process.OverallStatus.REJECTED)
        .order_by("-created_at")
        .first()
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


def _corrected_fields(scan: CardScan, values: dict) -> list[str]:
    proposed = (scan.draft or {}).get("fields", {})
    return sorted(
        name
        for name, value in values.items()
        if name in proposed and str(proposed[name].get("value", "")) != str(value or "")
    )
