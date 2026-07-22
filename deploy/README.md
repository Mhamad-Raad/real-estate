# deploy/

Deployment and local-runtime config for the Land-Allocation System.

> **Scope note:** only the **dev** compose lives here so far. The full **offline production
> packaging** (Nginx serving the static build, `docker save`/`load` image bundles, fixed-IP
> LAN, TLS, encryption, backup automation) is Iteration 7 — see the implementation plan.

## Dev stack (Docker) — recommended for prod parity

Postgres 16 + Django, pinned to **Python 3.12** so the container matches the Windows prod
runtime (and sidesteps the Python 3.14 C-extension wheel risk). Frontend stays on native Vite.

```bash
# From the repo root (needs a Docker runtime — see below):
docker compose -f deploy/docker-compose.dev.yml up -d --build
docker compose -f deploy/docker-compose.dev.yml exec backend python manage.py seed_dev
# Backend → http://127.0.0.1:8000   (Postgres published on host :5433)

# Frontend (native, separate terminal):
cd frontend && npm run dev          # http://localhost:5173 — proxies /api to :8000

# Tests inside the container:
docker compose -f deploy/docker-compose.dev.yml exec backend python manage.py test
# Tear down (keep data):  ... down      |  wipe data too:  ... down -v
```

Migrations run automatically on backend boot. Source is bind-mounted, so Django hot-reloads.

### Docker runtime on macOS (colima)

Docker Desktop is not required; this repo is developed with **colima** (CLI, no GUI):

```bash
brew install colima docker docker-compose
# add the compose plugin dir once, if `docker compose` isn't found:
#   ~/.docker/config.json → {"cliPluginsExtraDirs":["/opt/homebrew/lib/docker/cli-plugins"]}
colima start                 # boots the Linux VM
colima stop                  # when done
```

## Dev stack (native) — fastest inner loop

No container; uses Homebrew Postgres 17 on `:5432` and the local venv. See `backend/.env`
(`DB_HOST=127.0.0.1`).

```bash
brew services start postgresql@17
cd backend && .venv/bin/python manage.py runserver
cd frontend && npm run dev
```

The two paths are independent: the container DB (`:5433`, its own volume) and the native
Homebrew DB (`:5432`) do not clash, so you can switch between them freely.
