"""Write-side domain rules for clients — the sole place that writes client audit rows (§14.2)."""

from common.models import ActivityLog
from common.services import record_activity

from .models import Client


def create_client(*, data: dict, actor, request=None) -> Client:
    client = Client.objects.create(**data)
    record_activity(
        actor=actor,
        action=ActivityLog.Action.CREATE,
        entity_type="Client",
        entity_id=client.id,
        after={"full_name": client.full_name, "pid": client.pid},
        request=request,
    )
    return client
