# Host hardening — the office computer

What to do to the Windows PC itself, once, after the app is installed (§12). The app's own
defences are already in place; this is about the machine underneath them.

Everything here is done in Windows, by hand, and takes about twenty minutes. Nothing needs the
internet.

---

## 1. Keep the machine offline

The system is built to run with no internet at all, and every part of it — fonts, OCR models,
libraries — is bundled for that reason. The safest configuration is the one it was designed for.

- Do not connect the PC to Wi-Fi or to a router with internet access.
- When the second computer joins, connect the two through a **switch or a direct cable**, not
  through an internet-facing router.

If the machine must go online temporarily (driver install, Windows update), do it deliberately,
then disconnect again.

## 2. Windows Firewall — block inbound except the app

Control Panel → Windows Defender Firewall → **Advanced settings**.

- Leave the firewall **on** for all three profiles.
- Set the network the PC is on to **Private**, never Public/Guest — Windows applies different
  rules per profile, and the app is unreachable from the second computer on a Public profile.
- **Inbound rules:** allow **TCP 80** only (this is how the second computer reaches the app).
  Docker Desktop usually adds this rule itself when the stack first starts; confirm it exists and
  that nothing else has been opened.
- Leave **outbound** at the default (allow). Nothing in the stack calls out, and blocking outbound
  breaks Docker Desktop's own plumbing.

Do **not** open **5432** (the database) or **6379** (Redis). Production Compose deliberately does
not publish them — they are reachable only from inside Docker's own network.

## 3. Windows accounts

- The lawyers use a **Standard** account, not Administrator. Everyday work needs no admin rights,
  and the app runs regardless.
- One separate **Administrator** account with a real password, used only for installing and
  maintaining.
- Disable the **Guest** account.
- Set a screen lock: Settings → Accounts → Sign-in options → *Require sign-in when PC wakes*,
  and a short screen-off timeout. The computer is shared and the app's session lives as long as
  the browser is open.

A Windows password is **not** a substitute for disk encryption — see §5.

## 4. Updates and unattended restarts

- Windows Update: **notify, do not auto-restart**. A restart at 3 a.m. kills the nightly backup
  and the containers with it.
- Docker Desktop: turn **off** automatic updates (Settings → General). An update needs the
  internet the machine does not have, and a version change is a thing to do deliberately, with
  the app's images to hand.
- Docker Desktop: turn **on** *Start Docker Desktop when you sign in*, so the stack comes back
  after any restart.

## 5. Disk encryption

Covered separately, and the more important half is the **external backup drive** — it holds every
case and it leaves the building. A Windows password protects a running machine; it does nothing
against a drive read on another computer.

- Office PC: BitLocker on `C:` (needs Windows **Pro**).
- Backup drive: **BitLocker To Go** with a password.
- **Print both recovery keys** and lock them away. Lose them and the data is unrecoverable — by
  anyone.

*Status: deferred by the user, 2026-08-12. The PC is running unencrypted; the external drive is to
be encrypted when it is put into service.*

## 6. Secrets on the machine

- `deploy\.env` holds the database password and the signing key. It sits in the install folder;
  leave it there and do not copy it into a shared folder or email it.
- **Keep one copy on the external drive, beside the images.** A restored database cannot be opened
  without it, and a regenerated `SECRET_KEY` invalidates every signed token (§13.3).
- Anyone holding that file can read the database directly. It is not a password to hand around.
- The first Admin account is created with `manage.py create_admin` — it refuses weak, published,
  or username-containing passwords. Do not create users any other way.

## 7. What the app already does — no action needed

Listed so nobody adds a control that is already there, or removes one thinking it is missing.

- **No Django admin.** There is one write path into the data: the app's own API (It.8).
- **Login throttling** — 10 failed sign-ins per minute per computer, then a lockout (`§12`).
- **Audit trail cannot be edited or deleted**, by anyone, including through `psql` — enforced by
  database trigger (`common/0003`).
- **Nothing is ever hard-deleted** — every model is soft-delete only, FKs are `PROTECT`.
- **Database and Redis ports are not published** — unreachable from either computer's network.
- **The backend container runs as a non-root user.**
- **Security headers and a strict CSP** on every response; no CDN, no external font, no outbound
  call anywhere in the bundle.
- **Sessions end when the browser closes** — tokens live in `sessionStorage`, so the next lawyer
  at that desk is never signed in as the last one (§7.1).

## 8. Transport (HTTP, not HTTPS)

Decided 2026-08-12: the system goes live on **one** computer, so nothing crosses a network at all
and TLS would encrypt a conversation with itself. **Revisit when the second computer joins** —
that is the first moment traffic is on a wire, and it is the same job as fixing the server's IP,
because a self-signed certificate must carry that exact IP (§12).

---

## Quick checklist

- [ ] Machine is off the internet; LAN is a switch, not a router
- [ ] Firewall on, profile Private, inbound TCP 80 only, 5432/6379 closed
- [ ] Lawyers on Standard accounts; Guest disabled; screen lock on
- [ ] Windows Update set to notify; Docker auto-update off; Docker starts at sign-in
- [ ] BitLocker on `C:` and on the backup drive; both recovery keys printed and stored
- [ ] `deploy\.env` copied to the external drive and nowhere else
- [ ] First Admin created with `create_admin`, strong password
