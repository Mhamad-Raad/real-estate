# Production backend image — API and Celery worker (§2.3).
#
# One image, two commands. The web process needs LibreOffice as much as the worker does: the
# Templates screen renders a `.docx` preview inside the request (§6.6), so a slimmer web image
# would 500 the first time an admin looked at a letter. Two images would also double what has to
# be carried to the office on the external drive.
#
# Pinned to Python 3.12 for parity with the dev image — 3.14 has no wheels for some of the C
# extensions here, and finding that out on the office's machine is not the place.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# PGDG, so `pg_dump`/`pg_restore` match the PostgreSQL 16 server **exactly**. Debian's own client
# is 17, and its output carries `SET transaction_timeout`, which 16 rejects — the restore then
# completes "with errors ignored", which is not a restore. Found by running the drill (§13.3).
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl gnupg \
    && install -d /usr/share/postgresql-common/pgdg \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
         -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
    && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] \
https://apt.postgresql.org/pub/repos/apt $(. /etc/os-release && echo $VERSION_CODENAME)-pgdg main" \
         > /etc/apt/sources.list.d/pgdg.list \
    && rm -rf /var/lib/apt/lists/*

# Everything the app shells out to, installed **into the image** because the office has no
# internet (§12): LibreOffice renders the letters, the Noto fonts are what it renders them with —
# without them it silently substitutes a face and the Sorani letterforms come out wrong on a
# document that goes to a ministry. Tesseract + the Arabic script model read the ID cards (§6.2);
# there is no `ckb` model upstream, which is why `script-arab` is the one that matters.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libreoffice-writer-nogui \
        fonts-noto-core \
        tesseract-ocr \
        tesseract-ocr-ara \
        tesseract-ocr-eng \
        tesseract-ocr-script-arab \
        poppler-utils \
        postgresql-client-16 \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# The build stamp travels **into the image** (§2.6). Baked at build time rather than read from a
# mounted file, so an installed container can always answer "which build am I?" even if the repo
# is not on the office machine — which it will not be.
ARG APP_VERSION=0.0.0
ARG APP_BUILD=0
ENV APP_VERSION=${APP_VERSION} \
    APP_BUILD=${APP_BUILD}

# DRF's browsable API and its assets. Collected at build time so no writable static dir is needed
# at run time, and so the step cannot fail on a machine with no internet.
RUN DJANGO_DEBUG=1 SECRET_KEY=build-only python manage.py collectstatic --noinput

# Runs as a non-root user (§12). Root inside a container ignores file permissions, which is how a
# read-only data mount silently became writable in testing — and it is one less step for anything
# that escapes the container. The data root is chowned because the app writes the office's
# documents there.
RUN useradd --system --create-home --uid 10001 landalloc \
    && mkdir -p /data/documents /data/db-backups \
    && chown -R landalloc:landalloc /app /data
USER landalloc

EXPOSE 8000

# Gunicorn, not the dev server. Two workers suits two office computers; the timeout is generous
# because a compiled case merges every paper on a case and LibreOffice is not fast.
CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "2", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
