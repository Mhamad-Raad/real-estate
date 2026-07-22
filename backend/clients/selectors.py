"""Read/query logic for clients — search and duplicate detection (§3.7, §5.7)."""

from .models import Client


def search_clients(*, search: str = "", pid: str = ""):
    """List/search clients by exact PID or fuzzy full-name (trigram)."""
    qs = Client.objects.all()
    if pid:
        qs = qs.filter(pid=pid)
    if search:
        qs = qs.filter(full_name__trigram_similar=search)
    return qs.order_by("full_name")


def duplicate_matches(*, pid: str, mother_full_name: str, exclude_id=None):
    """Return (pid_matches, mother_name_matches) among active clients (§5.7).

    PID match = same person (hard duplicate). Mother-name fuzzy match = often a sibling
    (different PID) — the common false positive the admin override exists for.
    """
    active = Client.objects.all()
    if exclude_id:
        active = active.exclude(pk=exclude_id)
    pid_matches = list(active.filter(pid=pid)) if pid else []
    mother_matches = (
        list(active.filter(mother_full_name__trigram_similar=mother_full_name).exclude(pid=pid))
        if mother_full_name
        else []
    )
    return pid_matches, mother_matches
