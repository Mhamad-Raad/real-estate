"""Test helpers for the append-only audit trail (§11, migration common/0003).

Date-window tests need an audit row that is genuinely old. They used to write one and then
back-date it with `update()`, which the database now refuses — correctly, that is the whole point
of the trigger. `created_at` is `auto_now_add`, so the ORM will not let a caller set it either;
a raw INSERT is the honest way, and INSERT is the one thing the trail allows.
"""

import json
from contextlib import contextmanager
from unittest import mock

from django.db import connection

from .models import ActivityLog


@contextmanager
def broker_reachable():
    """Make `/health/`'s Redis probe succeed without a running broker.

    The two tests asserting a *healthy* 200 were the only ones in the suite that needed a real
    service, so they failed permanently on any machine without Redis — and a suite with a standing
    red baseline is one where a genuine new failure goes unnoticed. The failure-path tests already
    mock their dependency; this is the same treatment for the success path.
    """
    with mock.patch("kombu.Connection.ensure_connection", return_value=None):
        yield


def insert_backdated_activity(
    created_at,
    *,
    actor=None,
    action=ActivityLog.Action.UPDATE,
    entity_type="Process",
    entity_id="",
    after=None,
):
    """Insert an activity row stamped `created_at`. Returns its id. Tests only."""
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO activity_log "
            "(created_at, updated_at, action, entity_type, entity_id, actor_id, after) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb) RETURNING id",
            [
                created_at,
                created_at,
                action,
                entity_type,
                str(entity_id),
                actor.pk if actor else None,
                json.dumps(after) if after is not None else None,
            ],
        )
        return cursor.fetchone()[0]
