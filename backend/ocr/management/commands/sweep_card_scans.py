"""Scheduled recovery + cleanup for card scans (§6.3, §13).

Run from the host scheduler alongside the backup job — Task Scheduler on the Windows production
host, cron on the macOS dev machine. A management command rather than Celery Beat: the office runs
two computers with no internet, and one more always-on service is a worse trade than one more
scheduled script that logs what it did.

    python manage.py sweep_card_scans            # re-enqueue stuck reads, discard abandoned scans
    python manage.py sweep_card_scans --dry-run  # show what it would do
"""

from django.core.management.base import BaseCommand

from ocr import sweep
from ocr.models import CardScan


class Command(BaseCommand):
    help = "Re-enqueue stuck card readings and delete abandoned staged scans."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Report without changing anything.")

    def handle(self, *args, **options):
        if options["dry_run"]:
            stuck = CardScan.objects.filter(
                status__in=(CardScan.Status.PENDING, CardScan.Status.RUNNING),
                confirmed_at__isnull=True,
                discarded_at__isnull=True,
            ).exclude(file_path="")
            abandoned = CardScan.objects.filter(
                confirmed_at__isnull=True, discarded_at__isnull=True
            ).exclude(file_path="")
            self.stdout.write(
                f"would consider {stuck.count()} unfinished reading(s) and "
                f"{abandoned.count()} unconfirmed scan(s) against the age thresholds"
            )
            return

        requeued = sweep.requeue_stuck_scans()
        discarded = sweep.discard_abandoned_scans()
        self.stdout.write(
            self.style.SUCCESS(
                f"re-enqueued {len(requeued)} stuck reading(s); "
                f"discarded {len(discarded)} abandoned scan(s)"
            )
        )
