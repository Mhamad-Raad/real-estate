"""Write-side domain rules for clients — the sole place that writes client audit rows (§14.2)."""

from django.db import transaction
from rest_framework.exceptions import ValidationError

from common.models import ActivityLog
from common.services import record_activity

from common.validators import pid_taken

from .models import Client
from .selectors import pid_holder


def assert_pid_is_free(pid: str, *, exclude=None) -> None:
    """Reject a national ID another living client already holds — before the DB does.

    `ix_client_pid_active` would raise an IntegrityError here, which surfaces as an HTTP 500 and
    tells the lawyer nothing. It lands on the "no land twice" key, so every path that can write a
    PID — typed, scanned or corrected — goes through this and names the conflict (§3.7, §5.7).
    """
    if not pid:
        return
    conflict = pid_holder(pid=pid, exclude=exclude)
    if conflict:
        raise ValidationError(
            # The key, not a sentence: the office reads these screens in Sorani (§9). The holder's
            # name rides along after the colon — see `common.validators.pid_taken`.
            {"pid": pid_taken(conflict.full_name)}
        )


@transaction.atomic  # client row + its audit row commit together or not at all (§11)
def create_client(*, data: dict, actor, request=None) -> Client:
    client = Client.objects.create(**data, created_by=actor)
    record_activity(
        actor=actor,
        action=ActivityLog.Action.CREATE,
        entity_type="Client",
        entity_id=client.id,
        after={"full_name": client.full_name, "pid": client.pid},
        request=request,
    )
    return client
