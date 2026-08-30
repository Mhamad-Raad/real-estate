"""Refuse to run a destructive perf command against a real database (§13.1).

`seed_scale` and `measure_scale` both write — one adds 100,000 fabricated cases, the other creates
an Admin and forces `DEBUG` on. Each said "point it at a scratch database" in its docstring, which
is not a control: the office's database is one `DB_NAME` away, and a run against it mixes invented
citizens into real records with no way to tell them apart afterwards.
"""

from django.core.management.base import CommandError

# A scratch database has to be *named* like one. Anything else is assumed to hold real records.
SCRATCH_MARKERS = ("scale", "scratch", "perf", "test", "sandbox")

CONFIRM_FLAG = "--yes-not-production"


def add_scratch_argument(parser):
    parser.add_argument(
        CONFIRM_FLAG,
        action="store_true",
        dest="yes_not_production",
        help="Run against a database whose name does not look like a scratch one.",
    )


def require_scratch_database(db_name, confirmed):
    if any(marker in (db_name or "").lower() for marker in SCRATCH_MARKERS):
        return
    if confirmed:
        return
    raise CommandError(
        f"'{db_name}' does not look like a scratch database, and this command writes to it.\n"
        f"Use one named for the purpose (DB_NAME=landalloc_scale), or pass {CONFIRM_FLAG} if you "
        f"are certain it holds no real records."
    )
