"""Time the screens the office uses every day, at scale, and say which queries are unindexed (§13.1).

Runs the **real** endpoints through DRF, not hand-written SQL: a query that is fast on its own can
still be slow because the serializer triggers one more per row, and an N+1 is invisible to
`EXPLAIN`. Both the wall time and the query count are reported, because they fail differently —
100 fast queries and one slow one need opposite fixes.

    DB_NAME=landalloc_scale python manage.py measure_scale

Read-only. Point it at the seeded scratch database.
"""

import time

from django.core.management.base import BaseCommand
from django.db import connection, reset_queries
from django.test import Client as TestClient
from django.test.utils import CaptureQueriesContext

from accounts.models import User
from common.management.scratch_db import add_scratch_argument, require_scratch_database

# Anything the office waits on for longer than this reads as broken rather than slow.
SLOW_MS = 1_000
# A page showing 25 rows should not need a query per row.
MANY_QUERIES = 30


class Command(BaseCommand):
    help = "Measure the day-to-day endpoints against a seeded database."

    def add_arguments(self, parser):
        parser.add_argument("--explain", action="store_true", help="Print plans for slow queries.")
        add_scratch_argument(parser)

    def handle(self, *args, **options):
        from django.conf import settings

        require_scratch_database(
            settings.DATABASES["default"]["NAME"], options["yes_not_production"]
        )
        if not settings.DEBUG:
            # `CaptureQueriesContext` needs query logging, which Django only keeps with DEBUG on.
            settings.DEBUG = True
        # Django's test client sends `Host: testserver`, which production ALLOWED_HOSTS rejects —
        # so every request returned 400 and the first run reported thirteen endpoints at 5 ms with
        # **zero queries**. A measurement that succeeds while measuring nothing is the failure this
        # command exists to avoid, so the status code is checked, not just the clock.
        settings.ALLOWED_HOSTS = ["testserver", *settings.ALLOWED_HOSTS]

        # No password: the measurement authenticates with a token minted below, so the account
        # never needs to be signable-in. A known password here would be a working Admin login
        # left behind on whatever database this was pointed at.
        admin = User.objects.filter(role=User.Role.ADMIN).first() or User.objects.create_user(
            "perf_admin", password=None, role=User.Role.ADMIN
        )
        # A real JWT, not `force_login`: the API authenticates by bearer token only (§7), so a
        # session cookie leaves every request 401 — which the first run duly reported as thirteen
        # endpoints "needing attention" at 0 ms.
        from rest_framework_simplejwt.tokens import AccessToken

        api = TestClient(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(admin)}")

        from processes.models import Process

        sample = Process.objects.order_by("?").first()
        total = Process.objects.count()
        self.stdout.write(self.style.WARNING(f"Measuring against {total:,} cases\n"))

        checks = [
            ("processes: first page", "/api/v1/processes/"),
            ("processes: page 500", "/api/v1/processes/?page=500"),
            ("processes: search by name", "/api/v1/processes/?search=ئارام"),
            ("processes: search by code", "/api/v1/processes/?search=A5000"),
            ("processes: search by PID", "/api/v1/processes/?search=19700000"),
            ("processes: filter status+step", "/api/v1/processes/?overall_status=in_progress&current_step=3"),
            ("clients: search by name", "/api/v1/clients/?search=شیلان"),
            ("dashboard", "/api/v1/dashboard/"),
            ("activities: first page", "/api/v1/activities/"),
            ("reports: processes", "/api/v1/reports/processes/"),
            ("reports: users", "/api/v1/reports/users/"),
        ]
        if sample:
            checks.append(("case detail", f"/api/v1/processes/{sample.pk}/"))
            checks.append(("case documents", f"/api/v1/documents/?process={sample.pk}"))

        self.stdout.write(f"{'endpoint':32} {'ms':>8} {'queries':>8}  status")
        self.stdout.write("-" * 64)
        problems = []
        for label, url in checks:
            reset_queries()
            with CaptureQueriesContext(connection) as captured:
                started = time.perf_counter()
                response = api.get(url)
                elapsed = (time.perf_counter() - started) * 1000

            flags = []
            if elapsed > SLOW_MS:
                flags.append("SLOW")
            if len(captured) > MANY_QUERIES:
                flags.append("QUERIES")
            if response.status_code >= 400:
                flags.append(f"HTTP {response.status_code}")
            mark = " ".join(flags) or "ok"
            style = self.style.ERROR if flags else self.style.SUCCESS
            self.stdout.write(f"{label:32} {elapsed:>8.0f} {len(captured):>8}  {style(mark)}")

            if flags:
                problems.append((label, url, elapsed, captured.captured_queries))

        if not problems:
            self.stdout.write(self.style.SUCCESS("\nNothing over the thresholds."))
            return

        self.stdout.write(self.style.ERROR(f"\n{len(problems)} endpoint(s) need attention:\n"))
        for label, url, elapsed, queries in problems:
            self.stdout.write(f"  {label}  ({elapsed:.0f} ms, {len(queries)} queries)")
            slowest = sorted(queries, key=lambda q: float(q["time"]), reverse=True)[:2]
            for query in slowest:
                self.stdout.write(f"    {float(query['time']) * 1000:.0f} ms  {query['sql'][:150]}")
                if options["explain"]:
                    with connection.cursor() as cursor:
                        cursor.execute("EXPLAIN " + query["sql"])
                        for (line,) in cursor.fetchall()[:6]:
                            self.stdout.write(f"        {line}")
            self.stdout.write("")
