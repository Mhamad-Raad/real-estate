"""Fill in the institute rows that recorded no lawyer at all (UC-105).

New rows inherit the case's lawyer as they are created. This is for the ones filed **before** that
rule existed: they hold `NULL`, which is not "someone else did it" but "nobody wrote it down" — and
the compiled report prints that as a blank where a name belongs.

Deliberately a command and not a data migration. It writes to live records, so the office runs it
when they choose, after a backup, and can see what it did.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from common.models import ActivityLog
from common.services import record_activity

from ...models import ProcessInstituteEntry


class Command(BaseCommand):
    help = "Give every institute row with no lawyer the one its case was assigned to."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Write the changes. Without it the command only reports what it would do.",
        )

    def handle(self, *args, **options):
        # Only rows whose case actually has a lawyer to lend: a case with none would otherwise be
        # "filled" with the same blank it already had, and audited as though something happened.
        rows = (
            ProcessInstituteEntry.objects.filter(
                assigned_lawyer__isnull=True, process__assigned_lawyer__isnull=False
            )
            .select_related("process")
            .order_by("id")
        )
        found = rows.count()
        if not found:
            self.stdout.write(self.style.SUCCESS("Nothing to do — every institute row names a lawyer."))
            return
        if not options["apply"]:
            self.stdout.write(f"{found} institute row(s) record no lawyer. Re-run with --apply to fill them in.")
            return

        filled = 0
        for entry in rows:
            with transaction.atomic():
                entry.assigned_lawyer = entry.process.assigned_lawyer
                entry.version += 1
                entry.save(update_fields=["assigned_lawyer", "version", "updated_at"])
                # Audited like any other write (§11) — a field that changes with no trace is a
                # field nobody can explain later.
                record_activity(
                    actor=None,
                    action=ActivityLog.Action.UPDATE,
                    entity_type="ProcessInstituteEntry",
                    entity_id=entry.id,
                    before={"assigned_lawyer": None},
                    after={
                        "assigned_lawyer": entry.assigned_lawyer_id,
                        "reason": "backfilled from the case's lawyer (UC-105)",
                    },
                )
            filled += 1
        self.stdout.write(self.style.SUCCESS(f"Filled {filled} institute row(s)."))
