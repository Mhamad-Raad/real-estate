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

cat > "$BUNDLE/INSTALL.txt" <<TXT
========================================================================
  LAND ALLOCATION SYSTEM — ${APP_VERSION} (build ${APP_BUILD})
  How to install it on the office computer
========================================================================

Read this from top to bottom and do each step in order.
You do NOT need internet on the office computer. Everything is in this
folder. If a step says to type something, type it exactly.

There is a tick-list at the very bottom. Use it.


------------------------------------------------------------------------
  BEFORE YOU START
------------------------------------------------------------------------

Copy this whole folder from the USB drive ONTO the computer first
(for example to C:\LandAlloc). Do not run it from the USB stick.

You will need:
  - The Windows administrator password for this computer.
  - About one hour, mostly waiting.
  - A pen and paper. You will write down two passwords.


------------------------------------------------------------------------
  PART 1 — INSTALL THE TWO PROGRAMS      (about 20 minutes)
------------------------------------------------------------------------

The app runs inside a program called Docker. Docker needs another
program called WSL. Both are in the "installers" folder.

STEP 1.  Open the "installers" folder.

STEP 2.  Double-click:   wsl.2.7.11.0.x64.msi
         Click through it. Wait for it to finish.

         ** DO THIS ONE FIRST. **
         Docker needs WSL. If WSL is missing, Docker tries to download
         it from the internet — and this computer has none. Installing
         WSL first avoids that dead end completely.

STEP 3.  Double-click:   Docker Desktop Installer.exe
         Click through it. Accept the defaults.

STEP 4.  Restart the computer when Windows asks.

STEP 5.  After the restart, open Docker Desktop from the Start menu.
         Wait until it says "Engine running" (bottom-left, green).
         The first start can take a few minutes. Leave it open.

         ** If it says "virtualization support not detected" and the
            engine stops, do NOT go into the BIOS. Two Windows features
            are missing. The fix is at the bottom of this file, under
            "IF SOMETHING GOES WRONG" -> "Docker says virtualization is
            not supported". It takes five minutes and needs no internet.
            This happened on the first install. **


------------------------------------------------------------------------
  PART 2 — SET UP THE APP                (about 20 minutes)
------------------------------------------------------------------------

STEP 6.  Make the folder where the office's files will be kept.
         On the Desktop, create a new folder named exactly:

             LandAllocationData

         Its full path will look like:
             C:\Users\YOURNAME\Desktop\LandAllocationData

         (Replace YOURNAME with the Windows user name. You can see it in
          the address bar of any File Explorer window.)

STEP 7.  Open PowerShell inside this install folder:
         - Open the folder in File Explorer.
           ** "This install folder" is the one holding images.tar.gz,
              named landalloc-${APP_VERSION}-build${APP_BUILD}.
              What you copied from the USB CONTAINS that folder — open
              it first.
              Every command from STEP 8 on must run inside it, or you
              get "the system cannot find the file specified". **
         - Hold SHIFT and right-click on empty space inside it.
         - Choose "Open PowerShell window here".

         A black window opens. You will type the rest of the commands
         there. Press ENTER after each one and wait for it to finish
         before typing the next.

STEP 8.  Load the app. Type:

             docker load -i images.tar.gz

         This takes several minutes and prints a lot of lines.
         That is normal. Wait until you get your prompt back.

STEP 9.  Make the settings file. Type:

             copy .env.example .env

STEP 10. Open the new ".env" file in Notepad:

             notepad .env

         Find these four lines and fill them in. Everything after the
         "=" sign is what you change. Do not add spaces around the "=".

         DJANGO_SECRET_KEY=
             Type 30 or more random letters and numbers. Mash the
             keyboard. Nobody needs to remember this one.

         DB_PASSWORD=
             Make up a password. WRITE IT DOWN on your paper.
             ** LETTERS AND NUMBERS ONLY. No # and no @ — they break
                the file quietly, and the password is locked into the
                database the first time it starts. Getting this wrong
                is only fixable by wiping the database. **

         DATA_ROOT=
             The folder from STEP 6, but with FORWARD slashes:
                 C:/Users/YOURNAME/Desktop/LandAllocationData
             ** Forward slashes / — not backslashes \\ — even on Windows.
                This is the one people get wrong. **

         DJANGO_ALLOWED_HOSTS=
             Put:  localhost,127.0.0.1,THIS-COMPUTERS-IP

             To find the IP: in PowerShell type   ipconfig
             Look for "IPv4 Address". It looks like 192.168.1.10
             So the line becomes:
                 DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,192.168.1.10

             ** When the second computer is added later, add its address
                to this same line, separated by a comma. If you forget,
                that computer gets a blank error page. **

         Save the file (Ctrl+S) and close Notepad.

STEP 11. Start the app. Type:

             docker compose up -d

         Then WAIT ABOUT ONE MINUTE. It is starting the database.

STEP 12. Prepare the database. Type:

             docker compose exec backend python manage.py migrate

         Lots of "OK" lines will scroll past. Good.

STEP 13. Create your admin login. Type this, but replace "raad" with
         the username you want:

             docker compose exec backend python manage.py create_admin --username raad

         It will ask for a password.
         ** As you type the password NOTHING APPEARS on screen. That is
            normal, not a broken keyboard. Type it and press ENTER. **
         It will ask you to type it a second time to confirm.
         WRITE THIS PASSWORD DOWN. It refuses short or obvious ones.

STEP 14. Install the office's letter templates. Type:

             docker compose exec backend python manage.py install_templates

         ** This must come AFTER step 13, not before. **
         ** If you skip this step, nothing will print. No eligibility
            letter, no beneficiary list, no code list, no final case
            file, no request form. It will look like the app is broken. **


------------------------------------------------------------------------
  PART 3 — CHECK IT WORKS                (about 10 minutes)
------------------------------------------------------------------------

STEP 15. Open a web browser and go to:

             http://localhost/

         The login page should appear.
         At the bottom it must say:  ${APP_VERSION} (build ${APP_BUILD})
         If it says something else, tell the developer before continuing.

STEP 16. Log in with the username and password from STEP 13.

STEP 17. Add the office's categories.
         Go to the Categories screen (in the menu, admin only) and add
         each category the office uses.

         ** Do this before anyone opens a real case. A brand-new system
            has no categories, and a case cannot be finished without
            one — the case number is built from the category letter,
            like A1, A102, G2005. **

STEP 18. Make one test case from start to finish. Print something from
         it. Check the Kurdish and Arabic text reads correctly on paper.
         Then delete nothing — just leave it; it is your proof it works.


------------------------------------------------------------------------
  PART 4 — MAKE IT SAFE                  (about 20 minutes)
------------------------------------------------------------------------

STEP 19. Open "hardening.md" (in this folder) and work through it once.
         Firewall, Windows accounts, turning off automatic restarts.
         It is a short list and it is the computer's side of the
         security. The app's own side is already done.

STEP 20. Encrypt the external backup drive (BitLocker To Go).
         The steps are in hardening.md, section 5.
         ** PRINT THE RECOVERY KEY AND LOCK IT AWAY. If it is lost,
            nobody on earth can recover that drive. **

STEP 21. Copy the ".env" file from this folder onto the external drive
         and keep it there.
         ** Without it a backup cannot be restored. It holds the
            database password. Keep it off any shared folder. **


------------------------------------------------------------------------
  EVERY DAY / EVERY WEEK
------------------------------------------------------------------------

  The computer just needs to be ON. Docker Desktop starts by itself and
  the app comes back with it. Nobody has to type anything.

  A backup of the database is made automatically every night at 3am into:
      Desktop\LandAllocationData\db-backups

  ONCE A WEEK, plug in the external drive and copy BOTH of these onto it:
      Desktop\LandAllocationData\db-backups
      Desktop\LandAllocationData\documents

  That is the whole backup routine. The nightly part is automatic; the
  copy-to-the-drive part is not, and it is the part that survives the
  computer being stolen, dropped or wiped.

  "restore.md" explains how to put everything back if that ever happens,
  and how to practise it safely without touching the live system.


------------------------------------------------------------------------
  IF SOMETHING GOES WRONG
------------------------------------------------------------------------

  First: is Docker Desktop running? Open it, look for the green
  "Engine running". Most problems are just that it is not started.


  DOCKER SAYS VIRTUALIZATION IS NOT SUPPORTED, ENGINE STOPPED
  -----------------------------------------------------------
  This stopped the very first install (2026-08-13). It is not the BIOS.

  Task Manager showing "Virtualization: Enabled" does NOT mean Docker
  can run — that line only reports the processor. What is usually
  missing is two WINDOWS FEATURES.

  Open PowerShell AS ADMINISTRATOR (Start menu, type powershell,
  right-click it, "Run as administrator"). It opens in
  C:\Windows\system32 — that is correct for these three, they are
  system-wide. Type them one at a time:

      dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
      dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
      bcdedit /set hypervisorlaunchtype auto

  Then RESTART the computer and open Docker Desktop again. It should
  reach green.

  These install from the disk. They need no internet.

  Check WSL first if you want to be sure where the fault is. Type:

      wsl --version

  If a version prints, WSL is fine and the problem is the features
  above. Do not compare the number against anything you read online —
  that it prints at all is the pass. If it prints nothing or an error,
  WSL did not install: go back to STEP 2.

  ** Remember the two working folders. The three commands above run in
     system32. Everything from STEP 8 on runs INSIDE the install folder
     (STEP 7). Mixing them up is the other thing that catches people. **

  In PowerShell, inside this folder:

    Is everything up?
        docker compose ps
        Every line should say "running" or "healthy".

    What went wrong?
        docker compose logs backend --tail 50
        Read the last few lines. They usually name the problem.

    Is the app healthy?
        Open  http://localhost/api/v1/health/
        Every item must say "ok". If one says "error", that names the
        broken part — the database, redis, or the documents folder.

    Turn it off and on again (this does NOT delete anything):
        docker compose down
        docker compose up -d

  A blank or "400" page from the second computer almost always means its
  address is missing from DJANGO_ALLOWED_HOSTS in the .env file
  (see STEP 10). Add it, then run:  docker compose up -d


------------------------------------------------------------------------
  WHEN A NEW VERSION IS GIVEN TO YOU LATER
------------------------------------------------------------------------

  ** DO NOT start the new folder on its own, and never rename or move
     the folder you installed from. Docker names everything after that
     folder — INCLUDING THE DATABASE. Started from a differently named
     folder, the app comes up EMPTY: every case gone from the screen.
     The old data is still on the disk, but the app is no longer
     looking at it. This is measured behaviour, not a warning in
     principle. **

  So: you copy the NEW files INTO the folder you already use.

  1. BACK UP FIRST. It is the only way back. In PowerShell, inside
     your CURRENT install folder:

         docker compose exec backend python manage.py backup_db

     Then copy Desktop\LandAllocationData\db-backups onto the drive.

  2. Write down the name Docker uses for the app, so you can prove
     nothing moved:

         docker compose ls

     Note what the NAME column says. It must read the SAME at the end.

  3. Stop the app. This deletes nothing:

         docker compose down

  4. From the new folder on the drive, copy these ON TOP of the files
     of the same name in your CURRENT install folder:

         images.tar.gz
         docker-compose.yml
         VERSION
         nginx            (the whole folder)

     ** Do NOT copy .env.example over your .env, and do not touch
        .env itself. It holds your database password. **

  5. Back in PowerShell, still in your CURRENT folder:

         docker load -i images.tar.gz
         docker compose up -d
         docker compose exec backend python manage.py migrate

  6. CHECK, in this order:
         - docker compose ls shows the SAME name as step 2
         - http://localhost/ footer reads the new version
         - your cases are all still listed

     ** If the case list is empty, STOP. Do not enter anything, do not
        create a case. Call the developer. Nothing is lost — the app is
        pointed at the wrong database and it can be pointed back. **

  You do NOT need to run create_admin or install_templates again. Your
  logins, your categories and your documents are untouched by this.


------------------------------------------------------------------------
  TICK-LIST
------------------------------------------------------------------------

  [ ]  1. Folder copied from the USB onto the computer
  [ ]  2. WSL installed          (installers folder — FIRST)
  [ ]  3. Docker Desktop installed
  [ ]  4. Computer restarted
  [ ]  5. Docker Desktop open, says "Engine running"
  [ ]  6. LandAllocationData folder created on the Desktop
  [ ]  7. PowerShell open in this folder
  [ ]  8. docker load -i images.tar.gz
  [ ]  9. copy .env.example .env
  [ ] 10. .env filled in (4 lines) — DB password written down
  [ ] 11. docker compose up -d
  [ ] 12. migrate
  [ ] 13. create_admin — admin password written down
  [ ] 14. install_templates
  [ ] 15. http://localhost/ opens, footer reads ${APP_VERSION} (build ${APP_BUILD})
  [ ] 16. Logged in
  [ ] 17. Categories added
  [ ] 18. Test case created and printed, Kurdish/Arabic reads correctly
  [ ] 19. hardening.md done
  [ ] 20. Backup drive encrypted, recovery key printed and locked away
  [ ] 21. .env copied onto the backup drive
TXT

echo
echo "Wrote $BUNDLE"
du -sh "$BUNDLE"
echo
echo "Now drop the two installers into $BUNDLE/installers/ (see the note in there)."
