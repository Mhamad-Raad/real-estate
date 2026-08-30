# deploy/

| file | what it is |
|---|---|
| `docker-compose.dev.yml` | development: source bind-mounted, Django dev server, Vite run separately |
| `docker-compose.yml` | **production**: images only, Gunicorn, Nginx in front, no exposed DB port |
| `.env.example` | every setting the office install needs. Copy to `.env` — **that exact name** |
| `nginx/` | the site config + the security headers (included per-location; see the file) |
| `scripts/save-images.sh` | package images + config + runbook onto the drive for an offline install |

## Production, from nothing

    cd deploy
    cp .env.example .env      # fill in DJANGO_SECRET_KEY, DB_PASSWORD, DATA_ROOT, ALLOWED_HOSTS
    docker compose up -d
    docker compose exec backend python manage.py migrate
    docker compose exec backend python manage.py create_admin --username <name>

Then open the app and check the footer shows the build you expect.

## Building for the office

Always through `scripts/save-images.sh` — it sources `VERSION`, so the build stamp is baked into
the images. A bare `docker compose build` yields `0.0.0 (build 0)`.

---

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
