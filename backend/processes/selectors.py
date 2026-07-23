"""Read/query logic for processes — the search & filter contract (§3.7, §4.3)."""

from .models import Process


def search_processes(params) -> "list[Process]":
    """Filter by structured fields only: date, client PID, client name, category, status, lawyer,
    current step."""
    qs = Process.objects.select_related("client", "category", "assigned_lawyer", "parcel")

    pid = params.get("pid")
    if pid:
        qs = qs.filter(client__pid=pid)

    search = params.get("search")
    if search:
        qs = qs.filter(client__full_name__trigram_similar=search)

    # Exact-match list filters, incl. current_step so the list can be narrowed to a workflow step.
    for field in ("category", "overall_status", "assigned_lawyer", "current_step"):
        value = params.get(field)
        if value:
            qs = qs.filter(**{field: value})

    if params.get("created_after"):
        qs = qs.filter(created_at__date__gte=params["created_after"])
    if params.get("created_before"):
        qs = qs.filter(created_at__date__lte=params["created_before"])

    return qs.order_by("-created_at")
