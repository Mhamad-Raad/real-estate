# Running the Land-Allocation System (local dev)

Two independent ways to run the app locally:

- **[Method A — Docker](#method-a--docker-recommended)** — Postgres + Django in containers, pinned to
  Python 3.12 so behaviour matches the Windows production host. Recommended.
- **[Method B — Native](#method-b--native-fastest-inner-loop)** — Homebrew Postgres + a local Python
  venv. Fastest reload, no containers.

In **both** methods the **frontend runs natively** with Vite (`npm run dev`) — only the
backend/DB differ. The two methods are isolated (different databases and ports), so you can
switch between them freely without them clashing.

> Runtime data (DB + PDFs) lives outside the repo in `~/Desktop/LandAllocationData/` and is
> never committed. The full **offline production deployment** (Nginx, image bundles, LAN, TLS,
> backups, encryption) is Iteration 7 — this guide is dev only.

---

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Node.js | 20+ (using 24) | frontend |
| npm | 10+ | frontend |
| Docker | Desktop **or** colima | Method A only |
| Python | 3.12–3.14 | Method B only (via Homebrew) |
| PostgreSQL | 16/17 | Method B only (`brew install postgresql@17`) |

Ports used: **5173** (frontend), **8000** (backend), **5432** (native Postgres),
**5433** (Docker Postgres, published to the host).

> Inside Docker the backend reaches the database as **`db:5432`** (the compose service name on
> the internal network) — the host-published **5433** is only for connecting from your machine
> (e.g. a GUI client or `psql`). `backend/.env` sets `DB_HOST=127.0.0.1` for native dev; the
> compose file **overrides** it to `DB_HOST=db` so the container talks over the internal network.

---

## Configuration (required for both methods)

The backend reads its settings from `backend/.env`, which is **git-ignored** (absent on a fresh
clone). Create it once from the template before running either method:

```bash
cp backend/.env.example backend/.env
```

The defaults in the template already match this guide (database name, user, password). Docker
Compose references this file directly, so it must exist even for Method A.

---

## Method A — Docker (recommended)

### 1. Start a Docker engine

You need a running Docker daemon. Either works:

**Docker Desktop** — just launch the Docker Desktop app (whale icon) and wait until it says
"running". Then point the CLI at it:

```bash
docker context use desktop-linux   # Docker Desktop's context
```

**colima** (CLI alternative, no GUI):

```bash
colima start                       # boots a small Linux VM
docker context use colima
```

Check which engine the CLI is talking to and confirm it's up:

```bash
docker context show     # -> desktop-linux (Docker Desktop) or colima
docker info >/dev/null && echo "daemon OK"
```

> ⚠️ **Docker Desktop and colima are separate engines.** A container created under one is
> invisible to the other. If `docker compose ps` looks empty, you're probably pointed at a
> different context than the one that started the stack — switch with `docker context use …`.

### 2. Bring up the backend + database

From the repo root (`~/Desktop/Land-Allocation-System`):

```bash
docker compose -f deploy/docker-compose.dev.yml up -d --build
```

This builds the Django image (Python 3.12), starts Postgres 16, waits until the DB is healthy,
runs migrations automatically, and serves the API on **http://localhost:8000**.

> **Editing code vs. changing models.** Your `backend/` folder is bind-mounted, so ordinary code
> edits hot-reload with no rebuild — `--build` is only needed when `requirements.txt` changes.
> But adding/altering a **model field** still requires you to *generate* the migration yourself
> (only *applying* is automatic):
>
> ```bash
> docker compose -f deploy/docker-compose.dev.yml exec backend python manage.py makemigrations
> ```
>
> Commit the generated migration file; it re-applies automatically on the next backend boot.

Create the dev login accounts (first run only):

```bash
docker compose -f deploy/docker-compose.dev.yml exec backend python manage.py seed_dev
```

### 3. Start the frontend (separate terminal)

```bash
cd frontend
npm install          # first run only
npm run dev
```

Open **http://localhost:5173**. Vite proxies `/api` to the backend on `:8000`.

### 4. Stop / tear down

```bash
docker compose -f deploy/docker-compose.dev.yml down       # stop (keeps the database)
docker compose -f deploy/docker-compose.dev.yml down -v    # stop AND wipe the database
# then, if using colima:  colima stop
```

### Useful Docker commands

```bash
docker compose -f deploy/docker-compose.dev.yml ps            # container status
docker compose -f deploy/docker-compose.dev.yml logs -f backend   # tail backend logs
docker compose -f deploy/docker-compose.dev.yml restart backend
docker compose -f deploy/docker-compose.dev.yml exec backend python manage.py <cmd>
```

---

## Method B — Native (fastest inner loop)

### 1. Start Postgres and create the database (first run only)

```bash
brew services start postgresql@17

# One-time role + database (skip if already created):
psql -d postgres -c "CREATE ROLE landalloc LOGIN PASSWORD 'landalloc_dev_pw' CREATEDB;"
psql -d postgres -c "CREATE DATABASE landalloc_dev OWNER landalloc;"
```

Your `backend/.env` (created in [Configuration](#configuration-required-for-both-methods))
already points at this (`DB_HOST=127.0.0.1`, `DB_PORT=5432`). The `CREATEDB` grant is needed so
the test runner can create its throwaway test database.

### 2. Backend

```bash
cd backend
python3.14 -m venv .venv          # first run only (any Python 3.12–3.14)
.venv/bin/python -m pip install -r requirements.txt   # first run only
.venv/bin/python manage.py migrate
.venv/bin/python manage.py seed_dev                   # first run only
.venv/bin/python manage.py runserver                  # -> http://localhost:8000
```

### 3. Frontend (separate terminal)

```bash
cd frontend
npm install          # first run only
npm run dev          # -> http://localhost:5173
```

---

## Logging in

Dev-only seed accounts (created by `seed_dev` — not for production):

| Username | Password | Role |
|----------|----------|------|
| `admin` | `admin12345` | Administrator — sees all nav (reports, activities, users) |
| `lawyer` | `lawyer12345` | Lawyer — sees dashboard, clients, processes, settings |

`admin` is also a Django superuser: **http://localhost:8000/admin/**.

> The app currently ships the authenticated **shell** only (login, language/RTL switch,
> light/dark). Business data — clients, processes, land parcels — arrives in Iteration 1.

---

## Running the tests

```bash
# Backend (Docker):
docker compose -f deploy/docker-compose.dev.yml exec backend python manage.py test
# Backend (native):
cd backend && .venv/bin/python manage.py test

# Frontend:
cd frontend && npm test
```

---

## Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| `Cannot connect to the Docker daemon` | Engine not running — start Docker Desktop, or `colima start`. |
| `docker compose ps` is empty but the app ran | Wrong context — `docker context use desktop-linux` (or `colima`). |
| Port **8000** already in use | A native `runserver` (or old container) is up. Stop it: `lsof -ti:8000 -sTCP:LISTEN \| xargs kill`. |
| Port **5432** in use when starting Docker | Harmless — the Docker DB publishes on **5433**, not 5432. |
| `permission denied to create database` (native tests) | The `landalloc` role needs `CREATEDB`: `psql -d postgres -c "ALTER ROLE landalloc CREATEDB;"`. |
| Frontend loads but API calls fail | Backend not up on `:8000`, or you started the frontend before the backend finished migrating. |
| Changed backend code isn't reflected | Docker: source is bind-mounted and auto-reloads; if stuck, `... restart backend`. |
