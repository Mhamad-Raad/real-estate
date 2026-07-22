"""Audit service — the single place that writes ActivityLog rows (§11).

Domain services (create_process, save_step, login…) call `record_activity`; views and
signals never write audit directly. Keeping it here means the actor, IP, and before/after
context are always supplied explicitly at the point the change is made.
"""

from __future__ import annotations

from typing import Any

from .models import ActivityLog


def client_ip(request) -> str | None:
    """Best-effort client IP for audit attribution (LAN, behind Nginx in prod)."""
    if request is None:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def record_activity(
    *,
    actor,
    action: str,
    entity_type: str,
    entity_id: Any = "",
    before: dict | None = None,
    after: dict | None = None,
    request=None,
    ip_address: str | None = None,
) -> ActivityLog:
    """Append one immutable audit row. `actor` may be None for anonymous/failed logins."""
    return ActivityLog.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        before=before,
        after=after,
        ip_address=ip_address or client_ip(request),
    )
