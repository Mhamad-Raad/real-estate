"""Django settings for the Land-Allocation System (dev + prod-parity base)."""

from datetime import timedelta

from celery.schedules import crontab
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv
import os
import sys
import tempfile

BASE_DIR = Path(__file__).resolve().parent.parent
TESTING = "test" in sys.argv

# Load local .env (never committed); missing file is fine in CI/prod where env is set directly.
load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


INSECURE_DEFAULT_SECRET = "dev-insecure-change-me"
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", INSECURE_DEFAULT_SECRET)
# Defaults to **off**: a production host that never sets the variable must not boot into debug,
# where every error answers with a stack trace and ALLOWED_HOSTS stops being enforced. Dev turns
# it on explicitly in `.env` (see `.env.example`), which is the safe direction for a default to
# fail in (It.8).
DEBUG = env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

# Never boot production on the insecure dev defaults — fail loudly instead of silently.
# Skipped under `manage.py test`, which forces DEBUG off itself: a fresh clone with no `.env` must
# still be able to run the suite, and a test run is not a production boot.
if not DEBUG and not TESTING:
    if SECRET_KEY == INSECURE_DEFAULT_SECRET or len(SECRET_KEY) < 32:
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY must be set to a strong (32+ char) value when DEBUG is off."
        )
    if not ALLOWED_HOSTS:
        raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must be set when DEBUG is off.")

INSTALLED_APPS = [
    # `django.contrib.admin` is deliberately absent — see the note in config/urls.py. It writes
    # through neither the service layer nor the soft-delete rules, so leaving it installed would
    # keep a second, unaudited write path into the same tables.
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    # Third-party
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    # Local
    "common",
    "accounts",
    "catalog",
    "clients",
    "parcels",
    "processes",
    "documents",
    "reports",
    "ocr",
]

# Offline document file store (§2.5, §6.7) — lives OUTSIDE the repo, bind-mounted in prod.
_CONFIGURED_DOCUMENTS_ROOT = Path(
    os.getenv("DOCUMENTS_ROOT", str(BASE_DIR.parent / "LandAllocationData" / "documents"))
)
# Under `manage.py test` the store is forced to a throwaway directory. It used to rely on each
# test class remembering `@override_settings(DOCUMENTS_ROOT=...)`, and the classes that forgot
# wrote real PDFs into the office's archive — junk that outlives the run, in the one place this
# system can never hard-delete from. Making it structural means no future test can leak into it.
DOCUMENTS_ROOT = (
    Path(tempfile.mkdtemp(prefix="las-test-documents-")) if TESTING else _CONFIGURED_DOCUMENTS_ROOT
)
# Hard cap on uploaded PDF size (bytes) — reject anything larger before writing to disk.
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(25 * 1024 * 1024)))
# Separate, larger bound for files the SERVER produces (§10.3). The compiled case merges
# documents that were each already accepted, so the upload cap would reject a legitimate export
# of a large case; this is a runaway-merge backstop, not an input restriction.
MAX_GENERATED_BYTES = int(os.getenv("MAX_GENERATED_BYTES", str(200 * 1024 * 1024)))

# Admin-uploaded .docx letter templates (§3.5, §6.6) — kept beside the documents they generate.
# Named to stay clearly distinct from Django's own TEMPLATES setting below.
#
# Redirected under `manage.py test` for the same reason `DOCUMENTS_ROOT` is: isolation relied on
# each test class remembering `@override_settings(LETTER_TEMPLATES_ROOT=…)`, and the classes that
# forgot wrote real `.docx` files into the office's template directory (It.8 — five of them landed
# there during this review). The earlier note here claimed the tests need the *installed*
# templates; they do not — every test that renders one either builds it or installs it into a root
# it overrides itself.
LETTER_TEMPLATES_ROOT = (
    Path(tempfile.mkdtemp(prefix="las-test-templates-"))
    if TESTING
    else Path(os.getenv("LETTER_TEMPLATES_ROOT", str(_CONFIGURED_DOCUMENTS_ROOT / "_templates")))
)
# Headless LibreOffice does the .docx→PDF render (D5): it shapes RTL Sorani/Arabic correctly,
# which the lightweight HTML-to-PDF engines do not.
LIBREOFFICE_BIN = os.getenv("LIBREOFFICE_BIN", "soffice")
LIBREOFFICE_TIMEOUT_SECONDS = int(os.getenv("LIBREOFFICE_TIMEOUT_SECONDS", "120"))

# Frontend translation files, read by the test that proves every machine code the API emits has a
# label (§3.6). Compose mounts them read-only at /frontend_locales; native dev finds them in-repo.
FRONTEND_LOCALES_DIR = next(
    (
        p
        for p in (Path("/frontend_locales"), BASE_DIR.parent / "frontend" / "src" / "i18n" / "locales")
        if p.is_dir()
    ),
    None,
)

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME", "landalloc_dev"),
        "USER": os.getenv("DB_USER", "landalloc"),
        "PASSWORD": os.getenv("DB_PASSWORD", ""),
        "HOST": os.getenv("DB_HOST", "127.0.0.1"),
        "PORT": os.getenv("DB_PORT", "5432"),
    }
}

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Sorani is the primary UI language; timezone follows the office (Iraq).
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Baghdad"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_FILTER_BACKENDS": ("django_filters.rest_framework.DjangoFilterBackend",),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
}

# The access token stays short: it is the one sent on every request, and rotation makes its expiry
# invisible — the app refreshes silently and retries (§7.1).
#
# The refresh window is the office's call (UC-071). A day meant a fresh sign-in every morning; a
# week means they sign in about as often as they think about it. The trade-off is on the other
# side: this is a shared office computer, so a session left open stays usable for the whole week.
# Two things bound that — the token is blacklisted the moment it is spent (rotation) or the user
# signs out, and the machines are on an isolated LAN behind full-disk encryption (§2, §12).
# Overridable per environment so a stricter site can shorten it without a code change.
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(os.getenv("ACCESS_TOKEN_MINUTES", "30"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(os.getenv("REFRESH_TOKEN_DAYS", "7"))),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}

CORS_ALLOWED_ORIGINS = env_list(
    "CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
)

# Celery (§6.6) — LibreOffice startup is far too slow to sit on a request.
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
# A generation job that outlives this is wedged; kill it rather than hold the worker.
CELERY_TASK_TIME_LIMIT = 300
CELERY_TASK_SOFT_TIME_LIMIT = 270
# Under `manage.py test` tasks run inline, so the suite never needs a broker running.
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", TESTING)
CELERY_TASK_EAGER_PROPAGATES = True

# Scheduled work (§13.2, §6.3). Nothing ran on a schedule before this: `ocr/sweep.py` was written
# in It.5 and never wired to anything, so abandoned identity documents accumulated in `_staging`
# indefinitely and a reading lost to a reboot span for ever on the review screen.
#
# Requires `celery -A config beat` alongside the worker — a worker on its own runs none of these.
CELERY_BEAT_SCHEDULE = {
    # Nightly, before the office arrives, so the dump is ready to carry to the drive in the
    # morning and a long dump never overlaps the working day.
    "nightly-database-backup": {
        "task": "common.run_backup",
        "schedule": crontab(hour=3, minute=0),
    },
    # Hourly: a reading lost to a reboot should come back within the hour, not the next day.
    "requeue-stuck-scans": {
        "task": "ocr.requeue_stuck_scans",
        "schedule": crontab(minute=15),
    },
    # Daily is ample — the threshold it enforces is 14 days.
    "discard-abandoned-scans": {
        "task": "ocr.discard_abandoned_scans",
        "schedule": crontab(hour=4, minute=0),
    },
}
