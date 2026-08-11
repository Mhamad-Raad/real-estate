#!/usr/bin/env bash
# Package the stack for an office machine that has never seen the internet (§2.3, §12).
#
#   ./deploy/scripts/save-images.sh /Volumes/BACKUP-DRIVE
#
# Writes everything the office needs to install or update, onto the drive you name. Run this on a
# machine that CAN reach the internet — it builds the images first.
set -euo pipefail

DEST="${1:?usage: save-images.sh <destination-folder>}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# The build stamp is the package's identity: it names the folder and is what the office reads back
# on the About screen to confirm the update landed (§2.6).
#
# **This `source` is why the stack must be built through this script.** The stamp is baked into
# both images as build args; a bare `docker compose build` does not see `VERSION` and produces
# `0.0.0 (build 0)`. That sentinel is deliberate — an obviously-wrong stamp is safe, a plausible
# but stale one is not — but it also means an ad-hoc build must never be what reaches the office.
# shellcheck disable=SC1091
source "$ROOT/VERSION"
BUNDLE="$DEST/landalloc-${APP_VERSION}-build${APP_BUILD}"

echo "Building images for ${APP_VERSION} (build ${APP_BUILD})…"
docker compose -f "$ROOT/deploy/docker-compose.yml" build

mkdir -p "$BUNDLE"

# One archive for all four images. `docker save` deduplicates shared layers across them, so the
# combined file is far smaller than four separate ones — which matters on a USB drive.
echo "Saving images (this is the slow part — they carry LibreOffice and Tesseract)…"
# `:latest` is what the compose file asks for — see the note there. The build the office is
# actually running is read off the About screen, not off an image tag.
docker save \
  "landalloc-backend:latest" \
  "landalloc-frontend:latest" \
  postgres:16 \
  redis:7-alpine \
  | gzip > "$BUNDLE/images.tar.gz"

# The compose file, Nginx config and env template travel with the images: without them the images
# are unrunnable, and the office has no copy of this repository.
cp "$ROOT/deploy/docker-compose.yml"            "$BUNDLE/"
cp -R "$ROOT/deploy/nginx"                      "$BUNDLE/"
cp "$ROOT/deploy/.env.example"                  "$BUNDLE/"
cp "$ROOT/VERSION"                              "$BUNDLE/"
cp "$ROOT/docs/runbooks/restore.md"             "$BUNDLE/" 2>/dev/null || true

cat > "$BUNDLE/INSTALL.txt" <<TXT
Land Allocation — ${APP_VERSION} (build ${APP_BUILD})

On the office computer, with no internet:

  1. docker load < images.tar.gz
  2. cp .env.example .env          <-- the name MUST be exactly .env
     …then edit it: set SECRET_KEY, DB_PASSWORD, DATA_ROOT and DJANGO_ALLOWED_HOSTS
     (ALLOWED_HOSTS must list BOTH computers, or the second one gets a bare 400).
  3. docker compose up -d
  4. docker compose exec backend python manage.py migrate
  5. First install only:
       docker compose exec backend python manage.py create_admin --username <name>
     Updates: skip this — the accounts are in the database, which is not in these images.
  6. Check it: open http://localhost/ and confirm the footer reads ${APP_VERSION} (build ${APP_BUILD}).

Updating an existing install:
  * Take a backup FIRST — it is the only way back:
      docker compose exec backend python manage.py backup_db
  * Then steps 1, 3 and 4. The database survives: it lives in a Docker volume, not in the images.

Keep .env on this drive. A restored database cannot be opened without it.
TXT

echo
echo "Wrote $BUNDLE"
du -sh "$BUNDLE"
