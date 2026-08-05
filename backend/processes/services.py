"""Write-side domain rules for processes — the sole place that writes process audit rows.

Every mutation here is transactional and audited (§11, §14.2). The "no land twice" rule is
ultimately enforced by the DB index (§3.7); these services add the app-level dedup + override.
"""

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError

from clients.selectors import duplicate_matches
from clients.services import assert_pid_is_free, create_client
from common.locking import check_version
from common.models import ActivityLog
from common.services import record_activity

from . import status as step_status
from .models import DuplicateOverride, Process, ProcessInstituteEntry, ProcessStep

STEP_NUMBERS = range(1, 6)
LAST_STEP = 5


class MissingFiles(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Some steps still have missing files; an admin can force completion."
    default_code = "missing_files"


# Step fields a user may edit directly; `status` is always recomputed, never client-set (§3.6).
EDITABLE_STEP_FIELDS = ("start_date", "end_date", "out_of_city_flag")


class DuplicateAllocation(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "This client already has an active allocation."
    default_code = "duplicate_allocation"


def allocate_unique_code(category) -> str:
    """The next case number for `category` — `A1`, then `A2`, … (§3.8).

    **Must be called inside a transaction.** Two office computers opening a case in the same
    category would otherwise both read the same highest number and both write it; allocation is
    serialised by taking a row lock on the **category** itself, so the second waits for the first.
    `ix_process_unique_code` is the storage-level backstop if anything ever slips past — the same
    belt-and-braces shape as the "no land twice" guarantee (§3.7).

    Counts over `all_objects`, deliberately: a soft-deleted case keeps its number for ever, so the
    sequence is "highest ever issued + 1", never a count of the live rows. Gaps are correct.
    """
    from catalog.models import Category

    # The lock, not the value — this is what makes concurrent allocation safe.
    Category.all_objects.select_for_update().filter(pk=category.pk).first()

    prefix = category.code
    used = Process.all_objects.filter(unique_code__startswith=prefix).values_list(
        "unique_code", flat=True
    )
    highest = 0
    for code in used:
        tail = code[len(prefix) :]
        # Only `<prefix><digits>` counts; a code from a longer category code that merely starts
        # the same way (`A` vs `AB`) must not be read as this category's.
        if tail.isdigit():
            highest = max(highest, int(tail))
    return f"{prefix}{highest + 1}"


@transaction.atomic
def assert_code_is_available(code: str, category, *, exclude=None) -> None:
    """Vet a hand-picked case number before the index does (§3.8, UC-062).

    Two rules, both the office's own:

    * it must carry **this case's category letter**. The first character of a code *is* the
      category, the category is fixed for the life of the case (UC-059), and letters that have
      gone out quote the code — so a code that disagreed with its case would be a lie on paper.
    * it must never have been used, **including by deleted cases**. A number is retired for ever
      once issued; `all_objects` is what makes that true rather than "free again after a delete".

    A case with no category can hold no chosen code at all: `prefix` would be "" and every bare
    number would pass the first rule, which is not a rule.
    """
    prefix = category.code if category else ""
    # A machine code travels beside the sentence. The sentence is English like every other DRF
    # error, but this one a lawyer hits by simply mistyping — and every screen in this app is
    # localized (§9). So the screens read `code_error` and print it in the office's own language,
    # the same shape `in_use` already uses for a refused delete.
    if not prefix or not code.startswith(prefix) or not code[len(prefix):].isdigit():
        raise ValidationError(
            {
                "unique_code": (
                    f"A case number in this category looks like "
                    f"{prefix or 'A'}1, {prefix or 'A'}2, …"
                ),
                "code_error": "wrong_category",
                "expected_prefix": prefix,
            }
        )
    taken = Process.all_objects.filter(unique_code=code)
    if exclude is not None:
        taken = taken.exclude(pk=exclude.pk)
    if taken.exists():
        raise ValidationError(
            {
                "unique_code": f"{code} has already been used and cannot be reused.",
                "code_error": "already_used",
            }
        )


def create_process(
    *, client, assigned_lawyer, actor, category=None, request=None, unique_code="",
) -> Process:
    """Create a case + its five step placeholder rows. Returns HTTP 409 (not 500) if the
    client already has an active allocation — the DB index is the race-safe backstop (§5.7)."""
    if (
        Process.objects.filter(client=client)
        .exclude(overall_status=Process.OverallStatus.REJECTED)
        .exists()
    ):
        raise DuplicateAllocation()
    # Server-owned warning flag — never trust the client; recompute from the identity dedup (§5.7).
    report = duplicate_matches(
        pid=client.pid,
        mother_full_name=client.mother_full_name,
        spouse_pid=client.spouse_pid,
        exclude_id=client.id,
    )
    # A PID collision or a household already holding an allocation is a real duplicate. A similar
    # mother name is almost always a sibling, so it stays advisory and never gates the workflow
    # (§5.7). The household case is what gives this flag teeth again: `ix_client_pid_active`
    # already makes a bare PID collision unreachable here, but it cannot see `spouse_pid`.
    duplicate_flagged = report.is_duplicate
    similar_name_flagged = bool(report.mother_name)
    try:
        # Savepoint so an IntegrityError here can't poison the surrounding transaction.
        with transaction.atomic():
            process = Process.objects.create(
                client=client,
                assigned_lawyer=assigned_lawyer,
                category=category,
                # A number the office chose, or the next free one. Either way the allocator
                # reads "highest ever issued + 1" over `all_objects`, so choosing A15 while the
                # sequence sat at A12 simply moves it on — the next auto code is A16, and A13/A14
                # are retired unused rather than handed out later (§3.8, UC-062).
                unique_code=(unique_code or allocate_unique_code(category)) if category else "",
                duplicate_flagged=duplicate_flagged,
                similar_name_flagged=similar_name_flagged,
            )
            # Step 1 is never "proceeded into" — opening the case *is* starting it — so it takes
            # its start date here; the rest are stamped by `advance_step` (UC-050).
            today = timezone.now().date()
            ProcessStep.objects.bulk_create(
                [
                    ProcessStep(
                        process=process,
                        step_number=n,
                        start_date=today if n == 1 else None,
                    )
                    for n in STEP_NUMBERS
                ]
            )
    except IntegrityError:  # lost the race against the other computer — same clean 409
        raise DuplicateAllocation()
    record_activity(
        actor=actor,
        action=ActivityLog.Action.CREATE,
        entity_type="Process",
        entity_id=process.id,
        after={"client_id": client.id, "assigned_lawyer_id": assigned_lawyer.id},
        request=request,
    )
    return process


@transaction.atomic
def intake_process(
    *,
    client=None,
    client_data=None,
    assigned_lawyer,
    actor,
    category=None,
    land_id="",
    land_address="",
    unique_code="",
    request=None,
) -> Process:
    """Open a case from the Step-1 intake form — the beneficiary and their case commit together.

    Either the person is already on file (`client`) or they are created here from `client_data`.
    That is the office's real order: the card in the lawyer's hand creates the person *and* starts
    the case, as one act (§5, UC-024). Nothing is written unless all of it is — an abandoned form
    must leave no half-created case behind, because nothing here is ever hard-deleted (§11.1).
    """
    if (client is None) == (client_data is None):
        raise ValidationError(
            {"client": "Provide exactly one of an existing client or new client details."}
        )
    if client is None:
        # Named before the DB names it: `ix_client_pid_active` would raise an IntegrityError, which
        # reaches the lawyer as a 500 saying nothing (§3.7).
        assert_pid_is_free(client_data.get("pid"))
        client = create_client(data=client_data, actor=actor, request=request)
    # Fall back to the beneficiary's own category when the caller did not name one — re-applying
    # after a rejection (UC-028) posts only the client. Without this the new case would have no
    # category, and since the category is fixed at creation (UC-059) and the unique code derives
    # from it (§3.8), it could never acquire either. Not left to the caller: a case with no code
    # is a data-integrity hole, so the guarantee belongs on this side of the boundary (§7.2).
    if category is None:
        category = client.category
    if unique_code:
        assert_code_is_available(unique_code, category)
    process = create_process(
        client=client,
        assigned_lawyer=assigned_lawyer,
        category=category,
        actor=actor,
        unique_code=unique_code,
        request=request,
    )
    if land_id or land_address:
        process.land_id = land_id
        process.land_address = land_address
        process.save(update_fields=["land_id", "land_address", "updated_at"])
        # Both steps read these: Step 1 the address, Step 4 the `land_id` (UC-041). Recomputing
        # only Step 1 leaves Step 4 stored under the pre-save inputs — harmless while `land_id`
        # alone cannot change its status, but it is the same asymmetry the header PATCH had.
        recompute_step(process, 1)
        recompute_step(process, 4)
    return process


@transaction.atomic
def override_duplicate(
    *, process, admin, match_reason, reason, expected_version=None, request=None
) -> DuplicateOverride:
    """Admin-only: clear a fired duplicate warning, logged in both DuplicateOverride and audit."""
    # Same optimistic-lock guarantee as every other write: 409 if the process moved on, 400 if the
    # caller omitted `version` — a missing version must never silently skip the lock (§4.1).
    check_version(process, expected_version, required=True)
    process.duplicate_flagged = False
    process.version += 1
    process.save(update_fields=["duplicate_flagged", "version", "updated_at"])
    override = DuplicateOverride.objects.create(
        process=process,
        client=process.client,
        match_reason=match_reason,
        overridden_by=admin,
        reason=reason,
    )
    # Clearing the flag can be the last thing Step 1 was waiting on (§3.6).
    recompute_step(process, 1)
    record_activity(
        actor=admin,
        action=ActivityLog.Action.OVERRIDE,
        entity_type="Process",
        entity_id=process.id,
        before={"duplicate_flagged": True},
        after={"duplicate_flagged": False, "match_reason": match_reason, "reason": reason},
        request=request,
    )
    return override


def _advance_overall_status(process) -> None:
    """Keep overall_status honest after a step changes (§5.2, §5.3). Never touches rejected."""
    if process.overall_status == Process.OverallStatus.DRAFT:
        # draft → in_progress the moment any step holds real data.
        if process.steps.exclude(status=ProcessStep.Status.NOT_STARTED).exists():
            process.overall_status = Process.OverallStatus.IN_PROGRESS
            process.save(update_fields=["overall_status", "updated_at"])
    elif process.overall_status == Process.OverallStatus.COMPLETE:
        # A reopened/edited step can break completion — don't keep claiming "complete".
        if process.steps.exclude(status=ProcessStep.Status.COMPLETE).exists():
            process.overall_status = Process.OverallStatus.IN_PROGRESS
            process.save(update_fields=["overall_status", "updated_at"])


def recompute_step(process, step_number: int) -> ProcessStep:
    """Re-derive and persist one step's status after its data changed (docs/entries/fields).

    Server-derived, so it does NOT bump the optimistic-lock `version` (only user edits do)."""
    step = process.steps.get(step_number=step_number)
    new_status = step_status.compute_step_status(process, step_number, step)
    if new_status != step.status:
        step.status = new_status
        step.save(update_fields=["status", "updated_at"])
    _advance_overall_status(process)
    return step


def recompute_duplicate_flags(client) -> None:
    """Re-derive the duplicate flags after a client's identity keys changed (§5.7).

    `create_process` evaluates these once, which was enough while they depended only on `pid` —
    a value the PID index pins at creation. The household rule reads `spouse_pid`, and that
    routinely arrives *later*: a lawyer scans the beneficiary's card, opens the case, and only
    then scans the spouse's. Without this the conflict would be computed before the fact that
    creates it and would never fire.
    """
    report = duplicate_matches(
        pid=client.pid,
        mother_full_name=client.mother_full_name,
        spouse_pid=client.spouse_pid,
        exclude_id=client.id,
    )
    duplicate_flagged = report.is_duplicate
    similar_name_flagged = bool(report.mother_name)
    for process in Process.objects.filter(client=client):
        if (process.duplicate_flagged, process.similar_name_flagged) == (
            duplicate_flagged,
            similar_name_flagged,
        ):
            continue
        process.duplicate_flagged = duplicate_flagged
        process.similar_name_flagged = similar_name_flagged
        # Server-derived, so no `version` bump — only user edits move the optimistic lock.
        process.save(update_fields=["duplicate_flagged", "similar_name_flagged", "updated_at"])
        recompute_step(process, 1)  # `duplicate_flag` is part of Step 1's `missing` list


def recompute_client_steps(client) -> None:
    """Re-derive Step 1 for every process of a client whose own details changed.

    Marital status decides whether Step 1 owes a spouse ID, so without this the stored status
    (what the badges and list read) drifts from the live `missing` list (§3.6).
    """
    processes = (
        Process.objects.filter(client=client)
        .select_related("client")
        .prefetch_related("steps", "documents", "institute_entries__documents")
    )
    for process in processes:
        recompute_step(process, 1)


def recompute_client_state(client) -> None:
    """Everything the server derives from a client's own data, **in dependency order**.

    The duplicate flags feed Step 1's `missing` list (§3.6, §5.7), so they have to be refreshed
    before the step status is re-derived. One entry point rather than two calls at each site, so
    that ordering cannot be got wrong — and so a future derived value has one obvious home.
    """
    recompute_duplicate_flags(client)
    recompute_client_steps(client)


@transaction.atomic
def save_step(*, process, step_number, data, actor, expected_version=None, request=None) -> ProcessStep:
    """Partial per-step save (§5.2). Validates only present fields, recomputes status, audits."""
    step = process.steps.get(step_number=step_number)
    check_version(step, expected_version, required=True)  # optimistic lock on the step row
    before = {"status": step.status, "start_date": str(step.start_date), "end_date": str(step.end_date)}
    for field in EDITABLE_STEP_FIELDS:
        if field in data:
            setattr(step, field, data[field])
    step.status = step_status.compute_step_status(process, step_number, step)
    step.version += 1
    step.save()
    _advance_overall_status(process)
    record_activity(
        actor=actor,
        action=ActivityLog.Action.UPDATE,
        entity_type="ProcessStep",
        entity_id=step.id,
        before=before,
        after={"status": step.status, "start_date": str(step.start_date), "end_date": str(step.end_date)},
        request=request,
    )
    return step


@transaction.atomic
def advance_step(*, process, actor, expected_version=None, request=None) -> Process:
    """Unlock the next step (§5.2). `current_step` is the highest step the lawyer may open, so
    this is deliberately forward-only — an earlier step stays editable but can't re-lock later
    ones. Incompleteness is a UI warning, not a block: the lawyer may proceed anyway."""
    check_version(process, expected_version, required=True)
    if process.current_step >= LAST_STEP:
        raise ValidationError({"current_step": "The final step is already unlocked."})
    before = process.current_step
    process.current_step = before + 1
    process.version += 1
    process.save(update_fields=["current_step", "version", "updated_at"])

    # Proceeding into a step is the moment work on it starts, so that is when its start date is
    # stamped (UC-050) — the office was typing it by hand, and only step 2 even offered the field,
    # which is why the compiled cover sheet printed dates for step 2 alone (UC-058a).
    # **Only when blank**: a date entered by hand is usually a correction (the papers actually went
    # out last Tuesday), and overwriting it silently would discard that.
    opened = process.steps.filter(step_number=process.current_step).first()
    if opened is not None and opened.start_date is None:
        opened.start_date = timezone.now().date()
        opened.save(update_fields=["start_date", "updated_at"])
        # A start date is step data, so the step is no longer `not_started` — re-derive it, or the
        # badge contradicts the step's own contents (§3.6: status is re-derived wherever its
        # inputs change, and this write is one of those inputs).
        recompute_step(process, process.current_step)

    record_activity(
        actor=actor,
        action=ActivityLog.Action.UPDATE,
        entity_type="Process",
        entity_id=process.id,
        before={"current_step": before},
        after={"current_step": process.current_step},
        request=request,
    )
    return process


@transaction.atomic
def complete_process(*, process, actor, force=False, expected_version=None, request=None) -> Process:
    """Step-5 mark-complete (§5, §10.3). Blocks on missing files unless an admin forces it."""
    check_version(process, expected_version, required=True)
    for n in range(1, 5):
        recompute_step(process, n)
    prior_complete = all(
        s.status == ProcessStep.Status.COMPLETE for s in process.steps.filter(step_number__lt=5)
    )
    if not prior_complete and not force:
        raise MissingFiles()
    step5 = process.steps.get(step_number=5)
    step5.status = ProcessStep.Status.COMPLETE
    step5.version += 1
    step5.save(update_fields=["status", "version", "updated_at"])
    process.overall_status = Process.OverallStatus.COMPLETE
    process.current_step = 5
    # Recorded once, by the person who actually finished it — the compiled export prints this
    # (UC-044). Not overwritten on a later re-completion: the first person to close the case is
    # the one whose name is already on the paperwork that went out.
    if process.completed_by_id is None:
        process.completed_by = actor
    process.version += 1
    process.save(
        update_fields=["overall_status", "current_step", "completed_by", "version", "updated_at"]
    )
    record_activity(
        actor=actor,
        action=ActivityLog.Action.UPDATE,
        entity_type="Process",
        entity_id=process.id,
        after={"overall_status": process.overall_status, "forced": force},
        request=request,
    )
    return process


def release_client_with_case(process, *, actor, request=None) -> bool:
    """Soft-delete the beneficiary along with their deleted case, so they can be entered again.

    `ix_client_pid_active` is partial on `is_deleted=False`: a living client keeps holding their
    national ID. Deleting only the case therefore left the person locked out of the system —
    intake deliberately offers no "pick an existing client" (§5.7, UC-026), so re-entering them by
    hand hit the PID conflict and there was no way forward at all (UC-061).

    Skipped when another live case still needs the record: its documents, its letter and its
    compiled file all read the person from here, and deleting them out from under it would leave
    that case describing someone the register says is gone.
    """
    client = process.client
    if client is None or client.is_deleted:
        return False
    if Process.objects.filter(client=client).exclude(pk=process.pk).exists():
        return False

    client.is_deleted = True
    client.deleted_at = timezone.now()
    client.deleted_by = actor
    client.version += 1
    client.save(update_fields=["is_deleted", "deleted_at", "deleted_by", "version"])
    record_activity(
        actor=actor,
        action=ActivityLog.Action.DELETE,
        entity_type="Client",
        entity_id=client.id,
        after={"reason": "case deleted", "process_id": process.id},
        request=request,
    )
    return True


def restore_client_with_case(process, *, actor, request=None) -> bool:
    """Bring the beneficiary back with their restored case (the mirror of the above).

    A restore that left the client deleted would hand back a case whose person is not in the
    register. The PID may have been taken by a re-entry in the meantime, which is a legitimate
    outcome of freeing it — so it is checked first and reported as a 400 naming the conflict,
    rather than reaching the index and surfacing as a 500 that explains nothing.
    """
    client = process.client
    if client is None or not client.is_deleted:
        return False

    assert_pid_is_free(client.pid, exclude=client)
    client.is_deleted = False
    client.deleted_at = None
    client.deleted_by = None
    client.version += 1
    client.save(update_fields=["is_deleted", "deleted_at", "deleted_by", "version"])
    record_activity(
        actor=actor,
        action=ActivityLog.Action.RESTORE,
        entity_type="Client",
        entity_id=client.id,
        after={"reason": "case restored", "process_id": process.id},
        request=request,
    )
    return True
