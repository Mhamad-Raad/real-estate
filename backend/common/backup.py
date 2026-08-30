"""Scheduled `pg_dump` into the Desktop data folder (§13.2).

**Why a dump and not a file copy.** The office's plan is to drag the Desktop folder onto an
external drive by hand, which is exactly right for the documents — they are ordinary files. It
cannot work for the database: live Postgres is written to constantly, so copying its data
directory catches it mid-write. The copy *looks* fine — right size, no error — and fails on the
day it is needed. `pg_dump` takes a consistent point-in-time snapshot, restores into any
PostgreSQL 16, and is far smaller (measured on the dev data: 67 MB data directory → 186 KB dump).

**What this writes** lands beside the documents so one drag to the drive takes both:

    Desktop/LandAllocationData/
      documents/                     ← copied by hand
      db-backups/
        landalloc_2026-08-11T0300.dump
        landalloc_2026-08-11T0300.json   ← manifest

**The manifest is the part that matters at 3 a.m.** It records the app build and the applied
migration head, so whoever restores can tell whether the dump predates a schema change (§2.6) —
restoring a dump from an older migration head into a newer image is the failure a restore drill is
supposed to catch, and without this there is nothing to check it against.
"""

import json
import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.db import connection
from django.utils import timezone

from common.models import ActivityLog
from common.services import record_activity
from common.version import APP_VERSION, BUILD_NUMBER

# Kept beside `documents/` under the same data root, so the office copies one folder, not two.
BACKUP_DIRNAME = "db-backups"
# §13.2's rotation. Dailies cover "someone deleted it yesterday"; weeklies cover damage nobody
# noticed for a month — which is the case that actually loses data.
KEEP_DAILY = 14
KEEP_WEEKLY = 8
# `pg_dump -Fc`: compressed, and restorable selectively with `pg_restore`, unlike a plain SQL file.
DUMP_SUFFIX = ".dump"


def backup_dir() -> Path:
    """`<data root>/db-backups`, derived from where the documents live so the two cannot drift."""
    configured = os.getenv("DB_BACKUP_ROOT")
    if configured:
        return Path(configured)
    return Path(settings.DOCUMENTS_ROOT).parent / BACKUP_DIRNAME


def applied_migration_head() -> str:
    """The newest applied migration — what a restored dump must be reconciled against."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT app, name FROM django_migrations ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
    return f"{row[0]}.{row[1]}" if row else "none"


def _pg_dump(destination: Path) -> None:
    """Run `pg_dump` into `destination`. Raises `CalledProcessError` if it fails.

    The password travels in the environment, not the command line: an argument is visible to any
    process listing on the machine.
    """
    db = settings.DATABASES["default"]
    command = [
        "pg_dump",
        "--format=custom",
        f"--dbname={db['NAME']}",
        f"--username={db['USER']}",
        f"--host={db['HOST']}",
        f"--port={db['PORT']}",
        f"--file={destination}",
    ]
    env = {**os.environ, "PGPASSWORD": db["PASSWORD"]}
    subprocess.run(command, env=env, check=True, capture_output=True, timeout=60 * 30)


def run_backup(*, actor=None, now=None) -> Path:
    """Take a dump plus its manifest, prune old ones, and audit the result (§13.2).

    Writes to a `.part` file and renames on success. A rename is atomic, so a backup interrupted
    half-written never appears in the folder as a complete-looking dump — which is precisely the
    sort of file someone would later try to restore from.
    """
    now = now or timezone.now()
    directory = backup_dir()
    directory.mkdir(parents=True, exist_ok=True)

    stamp = now.strftime("%Y-%m-%dT%H%M")
    final = directory / f"{settings.DATABASES['default']['NAME']}_{stamp}{DUMP_SUFFIX}"
    partial = final.with_suffix(final.suffix + ".part")

    try:
        _pg_dump(partial)
        partial.rename(final)
    except Exception as exc:
        partial.unlink(missing_ok=True)
        record_activity(
            actor=actor,
            action=ActivityLog.Action.CREATE,
            entity_type="Backup",
            entity_id=stamp,
            after={"ok": False, "error": str(exc)[:500]},
        )
        raise

    manifest = {
        "created_at": now.isoformat(),
        "database": settings.DATABASES["default"]["NAME"],
        "dump_file": final.name,
        "size_bytes": final.stat().st_size,
        # The two facts a restorer needs and cannot recover from the dump itself.
        "app_version": APP_VERSION,
        "app_build": BUILD_NUMBER,
        "migration_head": applied_migration_head(),
        # Named, not copied: the documents are far too large to duplicate, and the office copies
        # that folder by hand. Recording it means a manifest describes a complete restore.
        "documents_root": str(settings.DOCUMENTS_ROOT),
    }
    final.with_suffix(".json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    pruned = prune_backups(now=now)
    record_activity(
        actor=actor,
        action=ActivityLog.Action.CREATE,
        entity_type="Backup",
        entity_id=stamp,
        after={"ok": True, "size_bytes": manifest["size_bytes"], "pruned": pruned},
    )
    return final


def prune_backups(*, now=None, keep_daily=KEEP_DAILY, keep_weekly=KEEP_WEEKLY) -> int:
    """Keep the last `keep_daily` days, plus one per week for `keep_weekly` weeks (§13.2).

    Deliberately keeps the **oldest** dump in each older week, not the newest: a week's first
    backup is the one taken before whatever went wrong during that week.
    """
    now = now or timezone.now()
    dumps = sorted(backup_dir().glob(f"*{DUMP_SUFFIX}"))
    if not dumps:
        return 0

    daily_cutoff = now - timedelta(days=keep_daily)
    weekly_cutoff = now - timedelta(weeks=keep_weekly)

    keep, by_week = set(), {}
    for dump in dumps:
        taken = _taken_at(dump)
        if taken is None or taken >= daily_cutoff:
            keep.add(dump)  # unparseable names are never deleted — better a stray file than a loss
            continue
        if taken < weekly_cutoff:
            continue
        week = taken.isocalendar()[:2]
        if week not in by_week or taken < _taken_at(by_week[week]):
            by_week[week] = dump
    keep.update(by_week.values())

    removed = 0
    for dump in dumps:
        if dump in keep:
            continue
        dump.unlink(missing_ok=True)
        dump.with_suffix(".json").unlink(missing_ok=True)
        removed += 1
    return removed


def _taken_at(dump: Path):
    """When a dump was taken, read from its name. `None` if the name is not ours."""
    try:
        return timezone.make_aware(
            datetime.strptime(dump.stem.rsplit("_", 1)[-1], "%Y-%m-%dT%H%M")
        )
    except (ValueError, IndexError):
        return None
