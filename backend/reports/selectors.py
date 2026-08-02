"""Aggregation for the home dashboard and the admin reports (§10.1, §10.2).

Read-only by design: nothing here writes, so nothing here touches the audit log. Every figure is
a single indexed `COUNT`/`GROUP BY` rather than a per-bucket query, so the whole dashboard is a
handful of queries no matter how much data accumulates.
"""

from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from clients.models import Client
from common.models import ActivityLog
from processes.models import Process, ProcessStep

STEP_NUMBERS = (1, 2, 3, 4, 5)


# A calendar week left the landing page almost entirely zeros every Monday morning and dropped the
# previous week's work out of view. One allocation here spans weeks, so the window has to roll (§10.1).
WINDOW_DAYS = 30


def window_start(now=None, *, days: int = WINDOW_DAYS):
    """Midnight, `days` ago, in the configured timezone."""
    now = now or timezone.localtime()
    start = now - timedelta(days=days)
    return start.replace(hour=0, minute=0, second=0, microsecond=0)


def _grouped(qs, field, keys):
    """`{key: count}` from one GROUP BY, with every expected key present.

    Absent buckets are filled with 0 on purpose — a chart with missing categories silently
    changes shape between refreshes, which reads as data loss.
    """
    counts = {row[field]: row["total"] for row in qs.values(field).annotate(total=Count("id"))}
    return {str(key): counts.get(key, 0) for key in keys}


def _by_lawyer_handled(since):
    """Distinct processes each user actually **worked on** in the window, from `activity_log`.

    Not "processes created and assigned to them" (§10.1): a lawyer progressing cases opened last
    month would report 0, which inverts the one thing the figure is for. `Count(distinct)` because
    a single case edited ten times is one case handled, and `login`/`logout` rows are excluded —
    they carry no entity and would otherwise credit simply signing in.
    """
    rows = (
        ActivityLog.objects.filter(
            entity_type="Process", created_at__gte=since, actor__isnull=False
        )
        .values("actor_id", "actor__username")
        .annotate(total=Count("entity_id", distinct=True))
        .order_by("-total", "actor__username")
    )
    return [
        {"lawyer_id": row["actor_id"], "username": row["actor__username"], "count": row["total"]}
        for row in rows
    ]


def _by_category(qs):
    return [
        {
            "category_id": row["category_id"],
            "name": row["category__name"] or "",
            "count": row["total"],
        }
        for row in qs.values("category_id", "category__name")
        .annotate(total=Count("id"))
        .order_by("-total", "category__name")
    ]


def _apply_range(qs, date_from, date_to):
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)
    return qs


def dashboard_stats(*, now=None) -> dict:
    """Everything the Home page renders, in one call (§10.1)."""
    since = window_start(now)
    processes = Process.objects.all()
    in_window = processes.filter(created_at__gte=since)
    statuses = Process.OverallStatus.values

    return {
        "window_start": since.date(),
        "window_days": WINDOW_DAYS,
        "clients_in_window": Client.objects.filter(created_at__gte=since).count(),
        "processes_in_window": in_window.count(),
        "processes_total": processes.count(),
        "processes_by_status": _grouped(processes, "overall_status", statuses),
        "processes_by_step": _grouped(processes, "current_step", STEP_NUMBERS),
        "by_lawyer_handled": _by_lawyer_handled(since),
        # Outstanding paperwork, counted two ways: how many steps are short a file, and how many
        # cases that actually affects — one case can be missing files on several steps.
        "steps_missing_files": ProcessStep.objects.filter(
            status=ProcessStep.Status.MISSING
        ).count(),
        "processes_missing_files": processes.filter(
            steps__status=ProcessStep.Status.MISSING
        ).distinct().count(),
        "duplicate_flagged": processes.filter(duplicate_flagged=True).count(),
        # Advisory only (§5.7) — surfaced so the similarity threshold can be judged on real data.
        "similar_name_flagged": processes.filter(similar_name_flagged=True).count(),
    }


def process_report(*, date_from=None, date_to=None, category=None) -> dict:
    """Throughput by status / category / step over a date range (§10.2)."""
    qs = _apply_range(Process.objects.all(), date_from, date_to)
    if category:
        qs = qs.filter(category_id=category)
    return {
        "total": qs.count(),
        "by_status": _grouped(qs, "overall_status", Process.OverallStatus.values),
        "by_step": _grouped(qs, "current_step", STEP_NUMBERS),
        "by_category": _by_category(qs),
    }


def user_report(*, date_from=None, date_to=None, category=None) -> list[dict]:
    """Per-lawyer workload: how much they were assigned in the range, and how much is finished."""
    qs = _apply_range(Process.objects.all(), date_from, date_to)
    if category:
        qs = qs.filter(category_id=category)
    rows = (
        qs.values("assigned_lawyer_id", "assigned_lawyer__username")
        .annotate(
            assigned=Count("id"),
            completed=Count("id", filter=Q(overall_status=Process.OverallStatus.COMPLETE)),
            in_progress=Count("id", filter=Q(overall_status=Process.OverallStatus.IN_PROGRESS)),
        )
        .order_by("-assigned", "assigned_lawyer__username")
    )
    return [
        {
            "lawyer_id": row["assigned_lawyer_id"],
            "username": row["assigned_lawyer__username"],
            "assigned": row["assigned"],
            "completed": row["completed"],
            "in_progress": row["in_progress"],
        }
        for row in rows
    ]
