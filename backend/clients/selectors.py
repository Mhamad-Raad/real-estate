"""Read/query logic for clients — search and duplicate detection (§3.7, §5.7)."""

from django.contrib.postgres.search import TrigramSimilarity

from .models import Client

# Postgres' `%` operator defaults to 0.3, which is far too loose for Kurdish/Arabic mother
# names — common given names cross it constantly. The name check is advisory only (identity is
# the government PID), so this threshold only controls how noisy that advisory is.
NAME_SIMILARITY_THRESHOLD = 0.5


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

    PID match = same person, the hard duplicate. Mother-name fuzzy match is **advisory only** —
    it is usually a sibling, and it exists to catch the one case the PID index cannot: the same
    person entered twice under two different PIDs (a keying typo or a reissued card).
    """
    active = Client.objects.all()
    if exclude_id:
        active = active.exclude(pk=exclude_id)
    pid_matches = list(active.filter(pid=pid)) if pid else []
    mother_matches = (
        list(
            # `trigram_similar` first so the GIN index does the coarse pass, then the stricter
            # threshold on top — filtering on the annotation alone would force a sequential scan.
            active.filter(mother_full_name__trigram_similar=mother_full_name)
            .exclude(pid=pid)
            .annotate(similarity=TrigramSimilarity("mother_full_name", mother_full_name))
            .filter(similarity__gte=NAME_SIMILARITY_THRESHOLD)
        )
        if mother_full_name
        else []
    )
    return pid_matches, mother_matches
