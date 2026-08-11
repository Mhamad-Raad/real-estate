#!/usr/bin/env bash
# Build ONE folder that installs the whole system on an offline Windows machine (§2.3, §12).
#
#     ./deploy/scripts/build-bundle.sh /Volumes/MY-DRIVE
#
# Run this HERE, on the development Mac, with internet. Copy the folder it writes to the office
# machine and follow the INSTALL.txt inside. Nothing else is needed there — no repository, no
# toolchain, no network.
#
# **Cross-builds for linux/amd64.** This Mac is arm64, and an arm64 image will not run on the
# office's x86-64 Windows PC: `docker load` succeeds and the containers then die with an exec
# format error, on the one machine with no way to rebuild. Override for an ARM target:
#     TARGET_ARCH=linux/arm64 ./deploy/scripts/build-bundle.sh /Volumes/MY-DRIVE
set -euo pipefail

DEST="${1:?usage: build-bundle.sh <destination-folder>}"
ARCH="${TARGET_ARCH:-linux/amd64}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# shellcheck disable=SC1091
source "$ROOT/VERSION"
BUNDLE="$DEST/landalloc-${APP_VERSION}-build${APP_BUILD}"

echo "Building ${APP_VERSION} (build ${APP_BUILD}) for ${ARCH}"
echo

# The app's own two images. `--load` puts them in the local daemon so `docker save` can reach them;
# buildx defaults to discarding the result, which produces an empty bundle and no error.
# `${svc}` braced throughout: a multi-byte character straight after a bare `$svc` makes bash read
# it as part of the variable name, which under `set -u` aborts the build with "unbound variable".
for svc in backend frontend; do
    echo "  building ${svc} ..."
    docker buildx build \
        --platform "$ARCH" \
        --build-arg "APP_VERSION=${APP_VERSION}" \
        --build-arg "APP_BUILD=${APP_BUILD}" \
        -t "landalloc-${svc}:latest" \
        --load \
        "${ROOT}/${svc}"
done

# Postgres and Redis must be pulled FOR THE TARGET too — the copies already on this Mac are arm64,
# and `docker save` would happily package those.
for img in postgres:16 redis:7-alpine; do
    echo "  pulling ${img} for ${ARCH} ..."
    docker pull --platform "$ARCH" "$img" >/dev/null
done

mkdir -p "$BUNDLE/installers"

echo "  saving images (slow - they carry LibreOffice and Tesseract) ..."
docker save \
    landalloc-backend:latest \
    landalloc-frontend:latest \
    postgres:16 \
    redis:7-alpine \
  | gzip > "$BUNDLE/images.tar.gz"

# Everything needed to run them. The office has no copy of this repository.
cp    "$ROOT/deploy/docker-compose.yml" "$BUNDLE/"
cp -R "$ROOT/deploy/nginx"              "$BUNDLE/"
cp    "$ROOT/deploy/.env.example"       "$BUNDLE/"
cp    "$ROOT/VERSION"                   "$BUNDLE/"
cp    "$ROOT/docs/runbooks/restore.md"  "$BUNDLE/"

cat > "$BUNDLE/installers/PUT-INSTALLERS-HERE.txt" <<'TXT'
Download these on ANY machine with internet and drop them in this folder before carrying the
drive to the office. They cannot be bundled automatically — they are Microsoft's and Docker's,
not ours, and both refuse to be redistributed by a script.

  1. Docker Desktop for Windows      https://docs.docker.com/desktop/install/windows-install/
  2. WSL2 kernel update package      https://aka.ms/wsl2kernel   (wsl_update_x64.msi)

The second is the one that catches people out: enabling WSL2 normally DOWNLOADS this from
Microsoft, which an offline machine cannot do. With the .msi here, it installs from the drive.
TXT

cat > "$BUNDLE/INSTALL.txt" <<TXT
Land Allocation — ${APP_VERSION} (build ${APP_BUILD})
Built for ${ARCH}

Everything needed is in this folder. The office machine needs no internet.

FIRST INSTALL
-------------
  1. Install Docker Desktop from installers/ (and the WSL2 kernel .msi if Windows asks).
     Restart when it tells you to.
  2. Open a terminal in this folder, then:
       docker load -i images.tar.gz
  3. copy .env.example .env
     Open .env and set:
       DJANGO_SECRET_KEY   a long random string
       DB_PASSWORD         a random password
       DATA_ROOT           C:/Users/<user>/Desktop/LandAllocationData
       DJANGO_ALLOWED_HOSTS   localhost,127.0.0.1,<this machine's LAN IP>
     ** List BOTH office computers' addresses, or the second gets a bare 400. **
  4. docker compose up -d
     docker compose exec backend python manage.py migrate
     docker compose exec backend python manage.py create_admin --username <name>
  5. Open http://localhost/ and check the footer reads ${APP_VERSION} (build ${APP_BUILD}).

UPDATING LATER
--------------
  1. BACK UP FIRST — it is the only way back:
       docker compose exec backend python manage.py backup_db
  2. docker load -i images.tar.gz
  3. docker compose up -d
     docker compose exec backend python manage.py migrate
  Keep your existing .env. The database is NOT in these images: it survives the update.

WHAT MUST STAY ON THE DRIVE
---------------------------
  .env  — a restored database cannot be opened without SECRET_KEY and DB_PASSWORD.

DAY TO DAY
----------
  Backups run nightly into Desktop/LandAllocationData/db-backups.
  Copy that folder AND Desktop/LandAllocationData/documents to the drive.
  restore.md explains how to put them back, and how to rehearse it safely.
TXT

echo
echo "Wrote $BUNDLE"
du -sh "$BUNDLE"
echo
echo "Now drop the two installers into $BUNDLE/installers/ (see the note in there)."
