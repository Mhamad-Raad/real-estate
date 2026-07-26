"""Write-side domain rules for processes — the sole place that writes process audit rows.

Every mutation here is transactional and audited (§11, §14.2). The "no land twice" rule is
ultimately enforced by the DB index (§3.7); these services add the app-level dedup + override.
"""

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError

from clients.selectors import duplicate_matches
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
    pid_matches, mother_matches = duplicate_matches(
        pid=client.pid, mother_full_name=client.mother_full_name, exclude_id=client.id
    )
    duplicate_flagged = bool(pid_matches or mother_matches)
    try:
        # Savepoint so an IntegrityError here can't poison the surrounding transaction.
        with transaction.atomic():
            process = Process.objects.create(
                client=client,
                assigned_lawyer=assigned_lawyer,
                category=category,
                duplicate_flagged=duplicate_flagged,
            )
            ProcessStep.objects.bulk_create(
                [ProcessStep(process=process, step_number=n) for n in STEP_NUMBERS]
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
    process.version += 1
    process.save(update_fields=["overall_status", "current_step", "version", "updated_at"])
    record_activity(
        actor=actor,
        action=ActivityLog.Action.UPDATE,
        entity_type="Process",
        entity_id=process.id,
        after={"overall_status": process.overall_status, "forced": force},
        request=request,
    )
    return process
