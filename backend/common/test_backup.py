"""The nightly backup and its rotation (§13.2).

`pg_dump` itself is exercised by the restore drill (`docs/runbooks/restore.md`), not here — a unit
test that shells out to a real database proves the environment, not the code. What these tests
hold is everything around it: that a half-written dump can never look complete, that the manifest
carries what a restorer needs, and that rotation keeps the right files.
"""

import json
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone

from common import backup as backup_module
from common.backup import prune_backups, run_backup
from common.models import ActivityLog


def _fake_dump(destination: Path) -> None:
    destination.write_bytes(b"PGDMP fake archive")


@override_settings(DOCUMENTS_ROOT=Path(tempfile.mkdtemp()) / "documents")
class BackupTests(TestCase):
    def setUp(self):
        self.directory = backup_module.backup_dir()
        self.directory.mkdir(parents=True, exist_ok=True)
        for stale in self.directory.iterdir():
            stale.unlink()

    def test_it_writes_a_dump_and_a_manifest_beside_the_documents(self):
        """One folder to drag to the drive, not two (§2.5)."""
        with mock.patch.object(backup_module, "_pg_dump", _fake_dump):
            path = run_backup()

        self.assertTrue(path.is_file())
        self.assertTrue(path.with_suffix(".json").is_file())
        self.assertEqual(path.parent.name, "db-backups")
        self.assertEqual(path.parent.parent, Path(backup_module.settings.DOCUMENTS_ROOT).parent)

    def test_the_manifest_records_what_a_restorer_cannot_infer(self):
        """The build and the migration head — how you tell a dump predates a schema change."""
        with mock.patch.object(backup_module, "_pg_dump", _fake_dump):
            path = run_backup()

        manifest = json.loads(path.with_suffix(".json").read_text())
        self.assertIn("app_version", manifest)
        self.assertIn("app_build", manifest)
        self.assertTrue(manifest["migration_head"], "no migration head recorded")
        self.assertEqual(manifest["dump_file"], path.name)
        # The documents are not copied here — but a manifest that did not name them would
        # describe half a restore.
        self.assertIn("documents_root", manifest)

    def test_a_failed_dump_leaves_no_file_that_looks_complete(self):
        """The nastiest failure: a truncated dump someone later restores from in good faith."""
        def explode(destination: Path):
            destination.write_bytes(b"half a dump")
            raise RuntimeError("pg_dump died")

        with mock.patch.object(backup_module, "_pg_dump", explode):
            with self.assertRaises(RuntimeError):
                run_backup()

        self.assertEqual(list(self.directory.glob("*.dump")), [])
        self.assertEqual(list(self.directory.glob("*.part")), [])

    def test_a_failed_backup_is_audited_as_a_failure(self):
        """Silence is how a broken backup survives for months."""
        with mock.patch.object(backup_module, "_pg_dump", side_effect=RuntimeError("nope")):
            with self.assertRaises(RuntimeError):
                run_backup()

        row = ActivityLog.objects.filter(entity_type="Backup").latest("id")
        self.assertFalse(row.after["ok"])

    def test_a_successful_backup_is_audited_too(self):
        with mock.patch.object(backup_module, "_pg_dump", _fake_dump):
            run_backup()

        row = ActivityLog.objects.filter(entity_type="Backup").latest("id")
        self.assertTrue(row.after["ok"])


@override_settings(DOCUMENTS_ROOT=Path(tempfile.mkdtemp()) / "documents")
class RotationTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.directory = backup_module.backup_dir()
        self.directory.mkdir(parents=True, exist_ok=True)
        # `override_settings(... mkdtemp())` is evaluated once per class, so every test here shares
        # one directory — without this, each test sees the previous one's dumps.
        for stale in self.directory.iterdir():
            stale.unlink()

    def _dump(self, days_ago: int):
        taken = self.now - timedelta(days=days_ago)
        path = self.directory / f"landalloc_{taken.strftime('%Y-%m-%dT%H%M')}.dump"
        path.write_bytes(b"x")
        path.with_suffix(".json").write_text("{}")
        return path

    def test_every_recent_daily_is_kept(self):
        recent = [self._dump(d) for d in range(0, 14)]

        prune_backups(now=self.now)

        for path in recent:
            self.assertTrue(path.is_file(), f"{path.name} should have been kept")

    def test_older_dumps_thin_to_one_per_week(self):
        """Asserts the rule, not a count: seven consecutive days can straddle two ISO weeks, so a
        hard-coded number would pass or fail depending on which day the suite runs."""
        for day in range(20, 27):
            self._dump(day)

        prune_backups(now=self.now)

        weeks = [
            backup_module._taken_at(p).isocalendar()[:2]
            for p in self.directory.glob("*.dump")
        ]
        self.assertTrue(weeks, "everything was pruned")
        self.assertEqual(len(weeks), len(set(weeks)), "more than one dump survived a week")

    def test_the_survivor_of_a_week_is_its_OLDEST(self):
        """A week's first backup is the one taken *before* whatever went wrong that week."""
        oldest = self._dump(26)
        self._dump(21)

        prune_backups(now=self.now)

        self.assertTrue(oldest.is_file())

    def test_dumps_beyond_the_weekly_window_go(self):
        ancient = self._dump(365)

        prune_backups(now=self.now)

        self.assertFalse(ancient.is_file())

    def test_a_manifest_is_removed_with_its_dump_and_never_alone(self):
        ancient = self._dump(365)

        prune_backups(now=self.now)

        self.assertFalse(ancient.with_suffix(".json").is_file())

    def test_a_file_it_does_not_recognise_is_never_deleted(self):
        """Someone's hand-made copy in the folder is not ours to remove."""
        stray = self.directory / "before_the_upgrade.dump"
        stray.write_bytes(b"x")

        prune_backups(now=self.now)

        self.assertTrue(stray.is_file())
