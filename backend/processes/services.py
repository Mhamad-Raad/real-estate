"""Write-side domain rules for processes — the sole place that writes process audit rows.

Every mutation here is transactional and audited (§11, §14.2). The "no land twice" rule is
ultimately enforced by the DB index (§3.7); these services add the app-level dedup + override.
"""

from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.exceptions import APIException

from clients.selectors import duplicate_matches
from common.locking import check_version
from common.models import ActivityLog
from common.services import record_activity

from .models import DuplicateOverride, Process, ProcessStep

STEP_NUMBERS = range(1, 6)


class DuplicateAllocation(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "This client already has an active allocation."
    default_code = "duplicate_allocation"


@transaction.atomic
def create_process(
    *, client, assigned_lawyer, actor, parcel=None, category=None, request=None,
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
                parcel=parcel,
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
    # Same optimistic-lock guarantee as every other write (409 if the process moved on).
    check_version(process, expected_version)
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
