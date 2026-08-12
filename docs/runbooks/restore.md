# Runbook — back up and restore

Two things hold all the data. Both live on the Desktop so one drag copies them:

```
Desktop/LandAllocationData/
  documents/     every scanned and generated PDF, plus the letter templates
  db-backups/    the nightly database dump + its manifest
```

Nothing else holds data. Redis is a job queue and rebuilds itself.

---

## Daily / weekly — what the office does

1. Plug in the external drive.
2. Copy **both** folders across. Overwrite the previous copy.
3. Eject.

That is the whole procedure. The dump is produced automatically at **03:00**; you are only
carrying it. Use two drives in rotation (§13.2) — a single drive is a single point of failure, and
it is usually plugged into the machine you are protecting against.

To take a dump **now** — before an update, or before anything risky:

```
docker compose -f deploy/docker-compose.dev.yml exec backend python manage.py backup_db
```

---

## Check a backup is actually happening

The folder should contain a new `.dump` most mornings:

```
ls -lt ~/Desktop/LandAllocationData/db-backups | head
```

A failed backup is recorded in the audit trail as `Backup … ok: false`, visible on the Activities
screen. **No new file and no failure row means the schedule is not running** — check that
`celery -A config beat` is up, not just the worker. The worker alone runs nothing on a schedule.

---

## Restore

> Read the manifest first. If `migration_head` is older than the running app's, the restore is
> crossing a schema change: restore, then run `migrate`. Restoring an old dump into a new image
> without migrating is the failure this manifest exists to make visible.

```bash
# 1. What am I restoring?
cat ~/Desktop/LandAllocationData/db-backups/<stamp>.json

# 2. Put the documents back (if they were lost too)
cp -a /Volumes/<drive>/LandAllocationData/documents ~/Desktop/LandAllocationData/

# 3. Stop the app so nothing writes mid-restore
docker compose -f deploy/docker-compose.dev.yml stop backend worker

# 4. Recreate the database empty
docker compose -f deploy/docker-compose.dev.yml exec db \
  psql -U landalloc -d postgres -c "DROP DATABASE IF EXISTS landalloc_dev"
docker compose -f deploy/docker-compose.dev.yml exec db \
  psql -U landalloc -d postgres -c "CREATE DATABASE landalloc_dev"

# 5. Restore. Expect NO errors — see the version note below.
docker compose -f deploy/docker-compose.dev.yml exec backend sh -c \
  'PGPASSWORD=$DB_PASSWORD pg_restore --no-owner --dbname=$DB_NAME \
     --username=$DB_USER --host=$DB_HOST --port=$DB_PORT /data/db-backups/<stamp>.dump'

# 6. Bring it back up, applying any newer migrations
docker compose -f deploy/docker-compose.dev.yml start backend worker
docker compose -f deploy/docker-compose.dev.yml exec backend python manage.py migrate
```

### Then prove it worked — do not skip this

Restoring without checking is how a bad backup goes unnoticed:

1. Sign in. The case list is populated.
2. Open a case you know. Its papers are listed **and open** — that proves the database and the
   documents folder match each other, not just that each survived.
3. Check the Activities screen still shows history.

---

## Rehearse it — on a scratch database

The drill below touches nothing live, so it is safe to run any time. Do it **before** you need it:

```bash
docker compose -f deploy/docker-compose.dev.yml exec db \
  psql -U landalloc -d postgres -c "CREATE DATABASE restore_drill"
docker compose -f deploy/docker-compose.dev.yml exec backend sh -c \
  'PGPASSWORD=$DB_PASSWORD pg_restore --no-owner --dbname=restore_drill \
     --username=$DB_USER --host=$DB_HOST --port=$DB_PORT /data/db-backups/<stamp>.dump'
docker compose -f deploy/docker-compose.dev.yml exec db \
  psql -U landalloc -d restore_drill -c "SELECT count(*) FROM process"
docker compose -f deploy/docker-compose.dev.yml exec db \
  psql -U landalloc -d postgres -c "DROP DATABASE restore_drill"
```

---

## Known good, and two things that will confuse you

**Drill run 2026-08-11 — clean.** 29 processes, 29 clients, 178 documents, 4 users restored with
**zero** `pg_restore` errors, and 112 of 117 live documents resolved to a real file.

**Re-run 2026-08-12 on 1.0.0 — clean, and it proves the append-only trigger survives a restore.**
`common/0003` made `activity_log` reject UPDATE/DELETE, which is exactly the kind of thing that can
turn a restore into a half-loaded database, so the drill was repeated against it. Counts matched
live (29 / 29 / 178, audit 896 vs 897 — the expected off-by-one below), **zero** `pg_restore`
errors, and both triggers came back and still refused a `DELETE` and an `UPDATE` in the restored
copy. Why it works: `pg_dump` puts triggers in the **post-data** section, so rows load by `COPY`
before the triggers exist — and `COPY` was never blocked anyway.

> **Rehearse into a scratch database, not over the live one.** This re-run used
> `CREATE DATABASE restore_drill` + `pg_restore --dbname=restore_drill`, so `landalloc_dev` was
> never dropped. Step 4's `DROP DATABASE` below is for a **real** recovery. For practice, use the
> scratch form — the pilot records are not reproducible.

- **The audit count is one lower in the restore.** Expected. The backup writes its own "a backup
  happened" audit row *after* the dump is taken, so that row cannot be inside it.
- **A few documents may not resolve to a file.** The live database had exactly the same 5, from
  earlier testing — the restore reproduced the live state faithfully, missing files included. If
  the counts differ from live, that is a real problem; if they match, it is pre-existing damage.

**The client version must match the server.** The first drill was run with `pg_dump` 17 against a
PostgreSQL 16 server: it emits `SET transaction_timeout`, which 16 rejects, and the restore
completed "with errors ignored". A backup that only *mostly* restores is not a backup. The backend
image therefore pins `postgresql-client-16`. If you ever upgrade PostgreSQL, upgrade both.
