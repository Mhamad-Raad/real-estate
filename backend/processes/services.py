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
from common.validators import STEP_END_BEFORE_START
from common.models import ActivityLog
from common.services import record_activity

from . import status as step_status
from .constants import FIRST_STEP, LAST_STEP, STEP_NUMBERS, WORKING_STEPS
from .models import DuplicateOverride, Process, ProcessInstituteEntry, ProcessStep


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
def create_process(
    *, client, assigned_lawyer, actor, category=None, request=None,
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
                # Issued here and never again: the category is fixed for the life of the case
                # (UC-059), so the letter can be trusted for as long as the code exists. The
                # office issues no numbers by hand — the system owns the sequence (UC-064).
                unique_code=allocate_unique_code(category) if category else "",
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
    process = create_process(
        client=client,
        assigned_lawyer=assigned_lawyer,
        category=category,
        actor=actor,
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


@transaction.atomic
def reassign_process(*, process, new_lawyer, actor, expected_version=None, request=None) -> Process:
    """Admin-only: hand a case to a different lawyer (2026-08-06).

    Assignment used to be fixed at creation, which was safe only while a lawyer could name nobody
    but themselves. Once any lawyer may open a case in a colleague's name, a mistyped name would
    otherwise be permanent — the wrong lawyer owning the case for good and the right one unable to
    edit it, since `assigned_lawyer` is on no update serializer. Admin-only for the same reason the
    duplicate override is: it moves work between people, so it is a decision with a name on it.

    Deliberately its own service and not a field on `ProcessUpdateSerializer`: the header `PATCH`
    is the everyday edit a lawyer makes, and reassignment must not ride along inside one.
    """
    check_version(process, expected_version, required=True)
    if new_lawyer.id == process.assigned_lawyer_id:
        return process  # naming the current assignee is not a change; don't bump or log one
    before = process.assigned_lawyer
    process.assigned_lawyer = new_lawyer
    process.version += 1
    process.save(update_fields=["assigned_lawyer", "version", "updated_at"])
    record_activity(
        actor=actor,
        action=ActivityLog.Action.UPDATE,
        entity_type="Process",
        entity_id=process.id,
        before={"assigned_lawyer": before.username if before else None},
        after={"assigned_lawyer": new_lawyer.username},
        request=request,
    )
    return process


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

    # A step cannot finish before it started. Checked **here** rather than on the serializer,
    # because this service writes the row by `setattr` and never runs one — a rule added there
    # would read like a guard and enforce nothing. Both dates print on the compiled cover sheet
    # (§10.3), so an inverted pair goes out on a signed government document.
    #
    # Only the ordering: whether a step date may be in the *future* is a question about how the
    # office works — a planned date is plausible — and inventing an answer would refuse real
    # paperwork. This pair is self-contradictory under any such policy.
    # Skipped for the roll-up step, which has no start date worth ordering against (UC-094) — and
    # cases opened before that change still carry a stamped one, so the check has to stand down
    # here rather than rely on the column being empty.
    if (
        step_number != LAST_STEP
        and step.start_date
        and step.end_date
        and step.end_date < step.start_date
    ):
        raise ValidationError({"end_date": STEP_END_BEFORE_START})
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


def _opening_date(process, *, previous_step: int):
    """The date a newly opened step starts on (UC-073).

    A case moves from one institute to the next, so the step being opened begins where the one
    before it finished — the office was re-typing that date on every step. Today is the fallback:
    the previous end date is often filled in later, and a step left without a start date reads as
    never started (§3.6) and shows as incomplete.
    """
    previous = process.steps.filter(step_number=previous_step).first()
    return (previous.end_date if previous else None) or timezone.now().date()


def settle_entry(entry) -> None:
    """What an institute write means for the step that owns it (§5.8).

    Lives here rather than on the viewset because it is a domain rule that writes: `views.py` is
    HTTP and permissions only (§14.2), and this decides a date that prints on a signed export.

    **Step 2 ends on its institute's approval date, not on the day the box was ticked (UC-090).**
    Step 2 has exactly one institute (UC-040), so "the step finished" and "that body decided" are
    the same event and the office already types the date of it on the entry. Stamping
    `timezone.now()` instead recorded the day the lawyer got round to the screen — often days
    later, and it printed on the cover sheet as the step's end.

    **Blank stays blank.** A decision recorded without a date leaves the step's end date empty for
    the office to fill, rather than inventing today; and an end date already on the step is left
    alone, because a date typed by hand is a correction.

    **Step 3 ends on the last of its institutes to decide (UC-090).** It carries three fixed bodies
    plus any out-of-city rows, so the step is not over until the furthest one is in — its end date
    is the **latest** approval date across them all, and it moves as later ones arrive. Blank-only
    would be wrong here in a way it is not for step 2: it would freeze on whichever institute
    happened to be decided first.

    That date only ever moves **forward**. A hand-typed date later than every approval is the
    office saying something this rule cannot see, and it survives; one earlier than an approval
    that demonstrably exists is corrected.
    """
    step = entry.step_number
    if step == 2:
        if entry.approval_status != entry.ApprovalStatus.PENDING and entry.approval_date:
            _close_step_on(entry.process, step, entry.approval_date, only_when_blank=True)
    elif step == 3:
        # **Decided institutes only**, exactly as step 2 above. The date box is editable while the
        # status is still `pending`, so a lawyer noting down when they expect an answer would
        # otherwise close the step on a body that has not answered — found in review, 2026-08-17.
        latest = max(
            (
                e.approval_date
                for e in entry.process.institute_entries.all()
                if e.step_number == 3
                and e.approval_date
                and e.approval_status != e.ApprovalStatus.PENDING
            ),
            default=None,
        )
        if latest:
            _close_step_on(entry.process, step, latest, only_when_blank=False)
    recompute_step(entry.process, entry.step_number)


def _close_step_on(process, step_number: int, date, *, only_when_blank: bool) -> None:
    """Date a step from its own paperwork, never backwards and never over a later hand-typed one."""
    step = process.steps.get(step_number=step_number)
    if step.end_date is not None and (only_when_blank or step.end_date >= date):
        return
    step.end_date = date
    step.save(update_fields=["end_date", "updated_at"])


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

    # **Leaving Step 1 is what ends it (UC-090).** Every other step has a finishing moment of its
    # own — an institute decision closes step 2 (§5.8), closing the case dates step 5 (UC-078) —
    # but nothing in step 1 ever marks one, so its end date stayed blank on every case in the
    # database. Proceeding out of it is that moment: the client's papers are gathered and the file
    # goes to the first institute. Deliberately **only** this step, on the office's instruction
    # (2026-08-17): steps 2–4 keep their typed end dates, because the day a lawyer walks out of an
    # institute's office is not the day they happen to open the next step on screen.
    #
    # Written before the start date below, so `_opening_date` reads a real value rather than
    # falling back to today — the two are the same date here, and saying so is the point.
    closed_on = None
    if before == FIRST_STEP:
        closing = process.steps.filter(step_number=before).first()
        if closing is not None and closing.end_date is None:
            closing.end_date = timezone.now().date()
            closing.save(update_fields=["end_date", "updated_at"])
            closed_on = closing.end_date
            # No `recompute_step`, unlike the start date below: step 1's status reads its category,
            # duplicate flag and papers (§3.6) and never its dates, so there is nothing to re-derive.

    # Proceeding into a step is the moment work on it starts, so that is when its start date is
    # stamped (UC-050) — the office was typing it by hand, and only step 2 even offered the field,
    # which is why the compiled cover sheet printed dates for step 2 alone (UC-058a).
    # **Only when blank**: a date entered by hand is usually a correction (the papers actually went
    # out last Tuesday), and overwriting it silently would discard that.
    # **Not the roll-up step (UC-094).** Step 5 holds no paperwork of its own — `_step_has_data`
    # says so — so a start date there dates nothing. Stamping one made the office's real closing
    # date, typed off a document dated earlier, fail the ordering check below against a date they
    # never entered.
    opened = process.steps.filter(step_number=process.current_step).first()
    if opened is not None and opened.start_date is None and process.current_step != LAST_STEP:
        opened.start_date = _opening_date(process, previous_step=before)
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
        # The opened step's start date is stamped by this call (UC-073) — recorded for the same
        # reason as the closing date in `complete_process`: a write nobody can trace is a write
        # outside the audit trail (§11).
        after={
            "current_step": process.current_step,
            "start_date": str(opened.start_date) if opened else None,
            # Same reason: a date this call wrote and nobody can trace is a write outside the
            # trail. `None` unless this call actually stamped one — it read back the *existing*
            # date when the office had already typed one, so the trail claimed a write that never
            # happened (found in review, 2026-08-17).
            "end_date_closed": str(closed_on) if closed_on else None,
        },
        request=request,
    )
    return process


@transaction.atomic
def complete_process(*, process, actor, force=False, expected_version=None, request=None) -> Process:
    """Step-5 mark-complete (§5, §10.3). Blocks on missing files unless an admin forces it."""
    check_version(process, expected_version, required=True)
    for n in WORKING_STEPS:
        recompute_step(process, n)
    # Asks each step what still *blocks*, not whether it is complete (UC-079, narrowed by UC-088):
    # the Step-4 institutes never hold a case open, but that step's municipality form and land
    # number do. A step's own status is left alone either way, so the case closes *over* an
    # unfinished step rather than pretending the step was done.
    prior_complete = not any(
        step_status.step_blocks_completion(process, s)
        for s in process.steps.filter(step_number__lt=LAST_STEP)
    )
    if not prior_complete and not force:
        raise MissingFiles()
    step5 = process.steps.get(step_number=LAST_STEP)
    step5.status = ProcessStep.Status.COMPLETE
    # Closing the case is what ends the final step (UC-078) — there is no step after it to
    # proceed into, so nothing else ever would. **Only when blank**, like every other stamped
    # date: a date typed by hand is a correction and must survive.
    if step5.end_date is None:
        step5.end_date = timezone.now().date()
    step5.version += 1
    step5.save(update_fields=["status", "end_date", "version", "updated_at"])
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
        # The closing date is written by this call and by nothing else (UC-078), so if it is not
        # recorded here the audit trail cannot say who dated the case or when — which is the whole
        # point of an append-only log (§11).
        after={
            "overall_status": process.overall_status,
            "forced": force,
            "step5_end_date": str(step5.end_date),
        },
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
