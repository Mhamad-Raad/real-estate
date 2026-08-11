"""Seed a large, realistic dataset to measure the app at the size the office is heading for (§13.1).

The whole system has been exercised against a few dozen cases. The office projects **70,000 to
100,000**. Nothing at 30 rows tells you which query does a sequential scan at 100,000 — and the
place to find that out is not the office's machine, offline, after they have filed 40,000.

**Writes only to the database it is pointed at.** Run it against a scratch one:

    createdb landalloc_scale
    DB_NAME=landalloc_scale python manage.py migrate
    DB_NAME=landalloc_scale python manage.py seed_scale --processes 100000

It creates **no files on disk** — document rows point at paths that do not exist. That is
deliberate: 100,000 cases of real PDFs is ~800 GB, and none of the queries being measured read a
file. What is measured is the database, which is what scales badly.
"""

import random
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from catalog.institutes import INSTITUTES
from catalog.models import Category
from clients.models import Client
from common.models import ActivityLog
from documents.models import Document
from processes.constants import STEP_NUMBERS
from processes.models import Process, ProcessInstituteEntry, ProcessStep

# Sorani given/family names, so the text indexes are exercised on the script they will really hold.
# A trigram index over Latin test data would say nothing about how it behaves on Arabic script.
FIRST = ["ئارام", "شیلان", "کاروان", "هێمن", "دلێر", "ژیان", "ڕێبین", "نەورۆز", "سۆزان", "بەختیار"]
FATHER = ["ئەحمەد", "عومەر", "مستەفا", "ڕەشید", "سەعید", "کەریم", "حەمە", "یاسین"]
FAMILY = ["مەحموود", "عەبدوڵا", "حەسەن", "ساڵح", "ئیبراهیم", "خالید", "نووری"]
PLACES = ["سلێمانی", "هەڵەبجە", "ڕانیە", "دوکان", "چەمچەماڵ", "کەلار"]


class Command(BaseCommand):
    help = "Seed a large dataset for performance measurement. Use a scratch database."

    def add_arguments(self, parser):
        parser.add_argument("--processes", type=int, default=100_000)
        parser.add_argument("--batch", type=int, default=2_000)
        parser.add_argument("--seed", type=int, default=1, help="Fixed, so runs are comparable.")

    def handle(self, *args, **options):
        total, batch = options["processes"], options["batch"]
        random.seed(options["seed"])

        from django.conf import settings

        db = settings.DATABASES["default"]["NAME"]
        self.stdout.write(self.style.WARNING(f"Seeding {total:,} cases into '{db}'"))

        # Numbering continues from what is already there. Restarting at 0 on a second run collides
        # with the first on `ix_client_pid_active` — the partial unique index that enforces "no
        # land twice" (§3.7) — and aborts the batch. Topping up a seeded database is the normal
        # way to grow one, so it has to work.
        start = Client.all_objects.count()
        if start:
            self.stdout.write(f"  continuing from {start:,} existing clients")

        lawyers = list(User.objects.filter(role=User.Role.LAWYER)[:8])
        if not lawyers:
            lawyers = [
                User.objects.create_user(f"perf_lawyer_{i}", password="pw12345678") for i in range(8)
            ]
        categories = list(Category.objects.all()) or [
            Category.objects.create(code=c, name=c) for c in ("A", "B", "C", "D")
        ]
        # (code, step) pairs, not codes alone: an institute belongs to exactly one step (§3.4),
        # and `bulk_create` bypasses the serializer that would have caught a mismatch — leaving
        # data no real case could produce, on the very joins being measured.
        institute_codes = [(code, step) for code, _key, step in INSTITUTES]
        today = timezone.now().date()

        made = 0
        while made < total:
            size = min(batch, total - made)
            self._batch(size, start + made, lawyers, categories, institute_codes, today)
            made += size
            self.stdout.write(f"  {made:,} / {total:,}", ending="\r")
            self.stdout.flush()

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"done — {made:,} cases"))
        for model in (Client, Process, ProcessStep, ProcessInstituteEntry, Document, ActivityLog):
            self.stdout.write(f"  {model.__name__:24} {model.objects.count():>10,}")

    @transaction.atomic
    def _batch(self, size, offset, lawyers, categories, institute_codes, today):
        """One transaction per batch — 100,000 rows in a single transaction is a long lock and a
        lot of memory, and a failure halfway would roll back the whole run."""
        clients = []
        for n in range(offset, offset + size):
            married = n % 3 == 0
            clients.append(
                Client(
                    full_name=f"{random.choice(FIRST)} {random.choice(FATHER)} {random.choice(FAMILY)}",
                    # Unique and realistic: `ix_client_pid_active` is a partial unique index, so a
                    # duplicate would abort the batch rather than measure anything.
                    # 12 digits, and unique for any `n` — the first two vary with the row so the
                    # value looks like a real national ID without the tail ever repeating.
                    pid=f"{19 + n % 60:02d}{n:010d}",
                    mother_full_name=f"{random.choice(FIRST)} {random.choice(FAMILY)}",
                    marital_status="married" if married else "single",
                    spouse_name=f"{random.choice(FIRST)} {random.choice(FAMILY)}" if married else "",
                    spouse_date_of_birth=date(1980, 1, 1) + timedelta(days=n % 7000) if married else None,
                    spouse_mother_full_name=random.choice(FAMILY) if married else "",
                    spouse_pid=f"{79 + n % 20:02d}{n:010d}" if married else "",
                    date_of_birth=date(1960, 1, 1) + timedelta(days=n % 14000),
                    place_of_birth=random.choice(PLACES),
                    phone=f"0770{n % 10000000:07d}",
                    address=f"{random.choice(PLACES)} — گەڕەکی {n % 40}",
                    category=categories[n % len(categories)],
                )
            )
        Client.objects.bulk_create(clients, batch_size=1_000)

        processes = []
        for n, client in enumerate(clients, start=offset):
            category = categories[n % len(categories)]
            processes.append(
                Process(
                    client=client,
                    category=category,
                    assigned_lawyer=lawyers[n % len(lawyers)],
                    unique_code=f"{category.code}{n + 1}",
                    current_step=(n % 5) + 1,
                    overall_status=("complete" if n % 7 == 0 else "in_progress"),
                    land_id=f"L-{n:07d}",
                    land_address=f"{random.choice(PLACES)} — پارچەی {n % 900}",
                )
            )
        Process.objects.bulk_create(processes, batch_size=1_000)

        steps, entries, documents, activity = [], [], [], []
        for n, process in enumerate(processes, start=offset):
            reached = process.current_step
            for step in STEP_NUMBERS:
                steps.append(
                    ProcessStep(
                        process=process,
                        step_number=step,
                        status=("complete" if step < reached else "in_progress" if step == reached else "not_started"),
                        start_date=today - timedelta(days=(200 - step * 10) % 365) if step <= reached else None,
                        end_date=today - timedelta(days=(180 - step * 10) % 365) if step < reached else None,
                    )
                )
            for i in range(2 if reached < 3 else 5):
                code, step = institute_codes[i % len(institute_codes)]
                entries.append(
                    ProcessInstituteEntry(
                        process=process,
                        step_number=step,
                        institute_code=code,
                        approval_status="approved" if i % 2 else "pending",
                    )
                )
            for i, doc_type in enumerate(["ClientID", "SignedAgreement", "RealEstate", "InstituteDoc"][:reached]):
                documents.append(
                    Document(
                        process=process,
                        step_number=min(i + 1, 5),
                        document_type=doc_type,
                        input_source=Document.InputSource.IMPORTED,
                        file_path=f"{process.category.code}/{process.unique_code}_{process.client.pid}/{doc_type}__{n:08d}.pdf",
                        display_filename=f"{process.unique_code}_{doc_type}.pdf",
                        size_bytes=250_000,
                        sha256=f"{n:064d}",
                        uploaded_by=process.assigned_lawyer,
                    )
                )
            # The audit log is append-only and never pruned (§11), so it outgrows every other
            # table. Measuring the Activities screen without it would measure the wrong thing.
            activity.append(
                ActivityLog(
                    actor=process.assigned_lawyer,
                    action=ActivityLog.Action.CREATE,
                    entity_type="Process",
                    entity_id=str(n),
                    after={"client_id": process.client_id},
                )
            )

        ProcessStep.objects.bulk_create(steps, batch_size=2_000)
        ProcessInstituteEntry.objects.bulk_create(entries, batch_size=2_000)
        Document.objects.bulk_create(documents, batch_size=2_000)
        ActivityLog.objects.bulk_create(activity, batch_size=2_000)
