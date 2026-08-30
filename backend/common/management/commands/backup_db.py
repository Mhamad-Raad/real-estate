"""Take a database backup now, without waiting for the nightly schedule (§13.2).

The supported manual path — before an update, before a risky change, or when someone simply wants
a fresh dump to carry to the drive. Same code the scheduled task runs, so what is tested by hand
is what runs at 3 a.m.
"""

from django.core.management.base import BaseCommand, CommandError

from common.backup import backup_dir, run_backup


class Command(BaseCommand):
    help = "Write a pg_dump + manifest into the Desktop data folder and prune old backups."

    def handle(self, *args, **options):
        try:
            path = run_backup()
        except Exception as exc:  # a failed backup must be loud, never a silent no-op
            raise CommandError(f"Backup FAILED: {exc}") from exc

        size_mb = path.stat().st_size / 1e6
        self.stdout.write(self.style.SUCCESS(f"wrote {path.name}  ({size_mb:.1f} MB)"))
        self.stdout.write(f"manifest: {path.with_suffix('.json').name}")
        self.stdout.write(f"folder:   {backup_dir()}")
        self.stdout.write(
            "\nCopy this folder AND `documents/` to the external drive — together they are the "
            "complete system data."
        )
