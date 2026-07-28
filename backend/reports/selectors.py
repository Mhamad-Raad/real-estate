"""Aggregation for the home dashboard and the admin reports (§10.1, §10.2).

Read-only by design: nothing here writes, so nothing here touches the audit log. Every figure is
a single indexed `COUNT`/`GROUP BY` rather than a per-bucket query, so the whole dashboard is a
handful of queries no matter how much data accumulates.
"""

from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from clients.models import Client
from processes.models import Process, ProcessStep

STEP_NUMBERS = (1, 2, 3, 4, 5)


def week_start(now=None):
    """Monday 00:00 of the current week, in the configured timezone."""
    now = now or timezone.localtime()
    monday = now - timedelta(days=now.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


def _grouped(qs, field, keys):
    """`{key: count}` from one GROUP BY, with every expected key present.

    Absent buckets are filled with 0 on purpose — a chart with missing categories silently
    changes shape between refreshes, which reads as data loss.
    """
    counts = {row[field]: row["total"] for row in qs.values(field).annotate(total=Count("id"))}
    return {str(key): counts.get(key, 0) for key in keys}


def _by_lawyer(qs):
    return [
        {
            "lawyer_id": row["assigned_lawyer_id"],
            "username": row["assigned_lawyer__username"],
            "count": row["total"],
        }
        for row in qs.values("assigned_lawyer_id", "assigned_lawyer__username")
        .annotate(total=Count("id"))
        .order_by("-total", "assigned_lawyer__username")
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
    since = week_start(now)
    processes = Process.objects.all()
    this_week = processes.filter(created_at__gte=since)
    statuses = Process.OverallStatus.values

    return {
        "week_start": since.date(),
        "clients_this_week": Client.objects.filter(created_at__gte=since).count(),
        "processes_this_week": this_week.count(),
        "processes_total": processes.count(),
        "processes_by_status": _grouped(processes, "overall_status", statuses),
        "processes_by_step": _grouped(processes, "current_step", STEP_NUMBERS),
        "by_lawyer_this_week": _by_lawyer(this_week),
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
