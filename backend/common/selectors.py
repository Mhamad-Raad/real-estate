"""Read/query logic for the audit trail (§11.3).

The Activities page is the only way the trail is ever read, and it is admin-only. Filtering is
kept to the indexed columns (`actor`, `action`, `entity_type`/`entity_id`, `created_at`) so the
page stays cheap as the log grows — it is append-only and never pruned.
"""

from .models import ActivityLog


def search_activities(params):
    """Filter the audit log by actor, action, entity and date range."""
    qs = ActivityLog.objects.select_related("actor")

    # Exact matches only — every one of these is an indexed column or part of a composite index.
    for field in ("actor", "action", "entity_type", "entity_id"):
        value = params.get(field)
        if value:
            qs = qs.filter(**{field: value})

    if params.get("created_after"):
        qs = qs.filter(created_at__date__gte=params["created_after"])
    if params.get("created_before"):
        qs = qs.filter(created_at__date__lte=params["created_before"])

    # Model Meta already orders by -created_at; restated so the contract is visible here.
    return qs.order_by("-created_at")


def entity_types():
    """The entity names actually present in the log, for the filter dropdown.

    Derived from the data rather than hard-coded: the list must not claim a type that was never
    written, and a new audited model should appear without a code change.
    """
    return list(
        ActivityLog.objects.order_by("entity_type")
        .values_list("entity_type", flat=True)
        .distinct()
    )


def actors():
    """Users who actually appear in the log.

    Taken from the trail, not from the active-user list: someone who has since been deactivated
    or soft-deleted still has history, and an audit page that cannot filter by a departed user
    fails at exactly the moment it matters most.
    """
    return [
        {"id": row["actor"], "username": row["actor__username"]}
        for row in ActivityLog.objects.filter(actor__isnull=False)
        .values("actor", "actor__username")
        .distinct()
        .order_by("actor__username")
    ]
