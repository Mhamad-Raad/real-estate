"""Read/query logic for processes — the search & filter contract (§3.7, §4.3)."""

from django.db.models import Q

from clients.selectors import name_or_pid

from .models import Process


def search_processes(params) -> "list[Process]":
    """Filter by structured fields only: date, client PID, client name, category, status, lawyer,
    current step."""
    qs = Process.objects.select_related("client", "category", "assigned_lawyer")

    pid = params.get("pid")
    if pid:
        qs = qs.filter(client__pid=pid)

    search = params.get("search")
    if search:
        # ONE box for the three things a lawyer actually knows about a case: the person's name,
        # their national ID, and the office's own case code (§4.3). The name/PID half is the same
        # rule as the Clients page — the two screens searched differently once and this one had
        # the identical partial-match defect (UC-004). `unique_code` joined them when the office
        # started quoting codes; `ix_process_code_trgm` keeps it an index scan, because the
        # uniqueness constraint is a btree and cannot serve `ILIKE '%…%'` (the same trap as
        # `ix_client_pid_trgm`, UC-005).
        qs = qs.filter(name_or_pid(search, prefix="client__") | Q(unique_code__icontains=search))

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
