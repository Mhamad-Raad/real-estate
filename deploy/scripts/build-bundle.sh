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

# A fresh named volume inherits its ownership from the image's directory at that path — so if
# `/generated` is missing from the image, Docker creates it **root-owned** and the non-root app
# cannot write a single letter. That shipped in 1.3.0 (build 4) and had to be repaired by hand on
# the office machine, because development runs as root and never sees it (UC-107). Checked here, on
# the image that is about to be packaged, so it can only ever be wrong once.
assert_generated_volume_is_writable() {
    local probe="landalloc-build-probe-$$"
    docker volume rm -f "$probe" >/dev/null 2>&1 || true
    if ! docker run --rm --platform "$ARCH" -v "$probe:/generated" \
        --entrypoint sh landalloc-backend:latest \
        -c 'mkdir -p /generated/letters && touch /generated/letters/.probe' >/dev/null 2>&1; then
        docker volume rm -f "$probe" >/dev/null 2>&1 || true
        echo "ERROR: the app cannot write to a fresh /generated volume — letters and lists would" >&2
        echo "       all fail with 'permission denied'. Check the mkdir/chown in backend/Dockerfile." >&2
        exit 1
    fi
    docker volume rm -f "$probe" >/dev/null 2>&1 || true
    echo "  /generated is writable by the app on a fresh volume"
}

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

assert_generated_volume_is_writable

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
# NOT a plain copy. The repo keeps `deploy/docker-compose.yml` one level under the root VERSION,
# so `env_file: - ../VERSION` is right there and wrong here — the bundle puts both files in ONE
# folder, `../VERSION` resolves to the bundle's parent, and Compose aborts the office's install
# with "env_file not found" (hit live, 2026-08-13). Rewritten as it is copied so the repo file,
# which dev runs against, stays correct.
sed 's|- \.\./VERSION|- VERSION|' "$ROOT/deploy/docker-compose.yml" > "$BUNDLE/docker-compose.yml"
# A silent no-op here ships a bundle that cannot start, so fail the build instead. Matches the
# list-item form only — a prose mention of `../VERSION` in a comment breaks nothing.
if grep -qE '^[[:space:]]*-[[:space:]]*\.\./VERSION' "$BUNDLE/docker-compose.yml"; then
    echo "ERROR: docker-compose.yml still references ../VERSION - the rewrite above missed it." >&2
    exit 1
fi
cp -R "$ROOT/deploy/nginx"              "$BUNDLE/"
cp    "$ROOT/deploy/.env.example"       "$BUNDLE/"
cp    "$ROOT/VERSION"                   "$BUNDLE/"
cp    "$ROOT/docs/runbooks/restore.md"  "$BUNDLE/"
cp    "$ROOT/docs/runbooks/hardening.md" "$BUNDLE/"

cat > "$BUNDLE/installers/PUT-INSTALLERS-HERE.txt" <<'TXT'
ONLY needed for a computer that has never had the app. If you are UPDATING a machine that
already runs it, ignore this folder completely — Docker and WSL are already installed there.

Download these on ANY machine with internet and drop them in this folder before carrying the
drive to the office. They cannot be bundled automatically — they are Microsoft's and Docker's,
not ours, and both refuse to be redistributed by a script.

  1. Docker Desktop for Windows
     https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe

  2. WSL — the x64 .msi from Microsoft's releases page
     https://github.com/microsoft/WSL/releases/latest
     Take the file named  wsl.<version>.x64.msi   (~260 MB).
     NOT the arm64 one, and NOT the .msixbundle.

** The old `aka.ms/wsl2kernel` / `wsl_update_x64.msi` link is DEAD — that CDN was retired, and it
is what every stale tutorial still points at (confirmed 2026-08-12). WSL now ships as a full
installer from GitHub, which is why it is 260 MB rather than a few. **

The WSL one is what catches people out: enabling WSL normally DOWNLOADS it from Microsoft, which
an offline machine cannot do. With the .msi on the drive, it installs from the drive.
TXT

# The two office sheets are **not written here**. They live in `docs/runbooks/` so the repo copy and
# the copy on the drive cannot drift — three corrections went unnoticed until an update was run by
# hand (2026-08-19). Only the version placeholders are substituted; nothing else expands.
render_sheet() {
    sed -e "s|\${APP_VERSION}|${APP_VERSION}|g" -e "s|\${APP_BUILD}|${APP_BUILD}|g" "$1" > "$2"
    # An unsubstituted placeholder would ship a sheet telling the office to look for a version
    # string that is not on their screen, so it fails the build rather than going out.
    if grep -q '\${APP_' "$2"; then
        echo "ERROR: $2 still contains an unsubstituted placeholder" >&2
        exit 1
    fi
}

render_sheet "$ROOT/docs/runbooks/install.md" "$BUNDLE/INSTALL.txt"

# The office already runs the app, so the fresh-install note is the wrong document to hand them.
# This one assumes Docker, WSL and a live database, and its whole job is to not lose that database.
render_sheet "$ROOT/docs/runbooks/update.md" "$BUNDLE/UPDATE.txt"

echo
echo "Wrote $BUNDLE"
du -sh "$BUNDLE"
echo
echo "Now drop the two installers into $BUNDLE/installers/ (see the note in there)."
