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
# `--platform` is REQUIRED, not tidiness. A pulled tag points at a multi-platform **index**, and a
# plain `docker save` tries to package every child listed in it — including the arm64 one that
# `pull --platform linux/amd64` never fetched. The result is not a wrong-architecture bundle but no
# bundle at all: `unable to create manifests file: NotFound: content digest sha256:… not found`,
# after the twenty minutes of building (hit on the 1.0.0 build, 2026-08-12). Restricting the save
# also makes the cross-arch guarantee explicit rather than implied by what happens to be cached.
docker save \
    --platform "$ARCH" \
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
cp    "$ROOT/docs/runbooks/hardening.md" "$BUNDLE/"

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
  1. Install WSL FIRST, from installers/:  wsl.2.7.11.0.x64.msi
     Then Docker Desktop:                  Docker Desktop Installer.exe
     Restart when Windows asks.
     ** WSL first, on purpose. Docker Desktop needs it, and if it is missing Docker
        tries to DOWNLOAD it — which this machine cannot do. Installing it first
        turns that dead end into a step that is already done. **
  2. Create the data folder before starting anything:
       C:\Users\<user>\Desktop\LandAllocationData
  3. Open a terminal (PowerShell) in this folder, then:
       docker load -i images.tar.gz
  4. copy .env.example .env
     Open .env in Notepad and set:
       DJANGO_SECRET_KEY   a long random string (30+ characters, any mix)
       DB_PASSWORD         a random password
       DATA_ROOT           C:/Users/<user>/Desktop/LandAllocationData
                           ** forward slashes, even on Windows **
       DJANGO_ALLOWED_HOSTS   localhost,127.0.0.1,<this machine's LAN IP>
     Find the LAN IP with:  ipconfig      (the IPv4 Address, e.g. 192.168.1.10)
     ** List BOTH office computers' addresses, or the second gets a bare 400. **
  5. docker compose up -d
     Wait about a minute the first time, then run the next three:

     docker compose exec backend python manage.py migrate
     docker compose exec backend python manage.py create_admin --username <name>
        It ASKS for the password — type it, it will not be shown. Write it down.
        It refuses weak or obvious ones; pick something long.
     docker compose exec backend python manage.py install_templates
     ** install_templates must come AFTER create_admin (it records who installed them).
        Without it the database has no letter templates and every generated document
        fails: the Step-1 eligibility letter, the beneficiary list, the code list,
        the Step-5 compiled case and the blank Request form. **
  6. Open http://localhost/ and check the footer reads ${APP_VERSION} (build ${APP_BUILD}).
     Sign in with the username and password from step 5.
     From the SECOND computer the address is  http://<the first machine's IP>/
  7. Add the office's CATEGORIES (Categories screen, admin only).
     A new database has none, and a case cannot be completed without one — the case
     number is the category's letter plus a counter (A1, A102, G2005).
  8. Work through hardening.md once — firewall, Windows accounts, update policy,
     secrets, disk encryption. Twenty minutes, and it is the machine's side of the
     security. The app's own side is already in place.

IF SOMETHING GOES WRONG
-----------------------
  See what is running:      docker compose ps
  Read the errors:          docker compose logs backend --tail 50
  Is it healthy?            open http://localhost/api/v1/health/
                            every check must say "ok"; it names the one that failed
  Start over cleanly:       docker compose down    (this keeps the database)

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
