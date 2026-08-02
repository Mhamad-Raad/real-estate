"""Read/query logic for clients — search and duplicate detection (§3.7, §5.7)."""

from typing import NamedTuple

from django.contrib.postgres.search import TrigramSimilarity
from django.db.models import Q

from .models import Client

# Postgres' `%` operator defaults to 0.3, which is far too loose for Kurdish/Arabic mother
# names — common given names cross it constantly. The name check is advisory only (identity is
# the government PID), so this threshold only controls how noisy that advisory is.
NAME_SIMILARITY_THRESHOLD = 0.5


def name_or_pid(term: str, *, prefix: str = "") -> Q:
    """One search box: match a name fragment **or** a national-ID fragment (§4.3, UC-004/UC-005).

    `icontains` (`ILIKE '%…%'`), never the pg_trgm `%` similarity operator: similarity divides by
    the union of both strings, so `'pers'` against `'Married Smoke Person'` scores 0.182 and misses
    — and a Kurdish name of 3–4 parts pushes even the person's own first name under the threshold.
    Both columns carry a trigram GIN index, which serves `ILIKE` as a bitmap index scan.

    `prefix` lets the Processes list reuse the identical rule across its `client` FK, so the two
    screens cannot drift apart again.
    """
    return Q(**{f"{prefix}full_name__icontains": term}) | Q(**{f"{prefix}pid__icontains": term})


def search_clients(*, search: str = "", pid: str = ""):
    """List/search clients: `pid` stays an exact filter; `search` is the fuzzy name-or-ID box."""
    qs = Client.objects.all()
    if pid:
        qs = qs.filter(pid=pid)
    if search:
        qs = qs.filter(name_or_pid(search))
    return qs.order_by("full_name")


def household_matches(*, pid: str, spouse_pid: str = "", exclude_id=None):
    """Clients already covered by an allocation as the same **household** (§3.7, §5.7).

    A married couple is one household and may be allocated land once, so two directions have to
    be checked and they are not symmetrical in the data:

    * this applicant is recorded as somebody else's **spouse** — the household already applied
      through the other partner;
    * this applicant's **spouse** is already a beneficiary in their own right.

    Neither is reachable by `ix_client_pid_active`, which only knows about the `pid` column. This
    is the one duplicate rule that genuinely lives in the application layer, because "no row's
    `pid` may equal any other row's `spouse_pid`" is a cross-row condition a unique index cannot
    express. The admin override (§5.7) therefore matters here in a way it no longer does for PID.
    """
    active = Client.objects.all()
    if exclude_id:
        active = active.exclude(pk=exclude_id)

    matches = []
    if pid:
        matches += list(active.filter(spouse_pid=pid))
    if spouse_pid:
        # Their spouse is on file as a beneficiary, or as someone else's spouse again.
        matches += list(active.filter(Q(pid=spouse_pid) | Q(spouse_pid=spouse_pid)))
    # One client can match on both counts; the caller wants each person once.
    return list({client.pk: client for client in matches}.values())


class DuplicateReport(NamedTuple):
    """The three kinds of match, kept apart because they mean different things to a lawyer.

    `pid` and `household` are both hard duplicates, but a screen that lumped them together would
    tell someone "same National ID" about a person whose ID is nothing like theirs.
    """

    pid: list
    household: list
    mother_name: list

    @property
    def is_duplicate(self) -> bool:
        """The hard duplicates — what `Process.duplicate_flagged` is derived from (§5.7)."""
        return bool(self.pid or self.household)


def duplicate_matches(
    *, pid: str, mother_full_name: str, spouse_pid: str = "", exclude_id=None
) -> DuplicateReport:
    """Everything that might make this person a duplicate, among active clients (§5.7).

    PID match = the same person twice, the hard duplicate. Household match = this person and an
    existing beneficiary are a married couple, which may hold one allocation between them — also
    hard. Mother-name fuzzy match is **advisory only**: it is usually a sibling, and it exists to
    catch the one case the PID index cannot, the same person entered under two different PIDs (a
    keying typo or a reissued card).
    """
    active = Client.objects.all()
    if exclude_id:
        active = active.exclude(pk=exclude_id)
    pid_matches = list(active.filter(pid=pid)) if pid else []
    household = [
        match
        for match in household_matches(pid=pid, spouse_pid=spouse_pid, exclude_id=exclude_id)
        if match.pk not in {c.pk for c in pid_matches}
    ]
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
    return DuplicateReport(pid=pid_matches, household=household, mother_name=mother_matches)
