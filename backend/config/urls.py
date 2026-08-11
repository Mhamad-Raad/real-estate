"""Root URL config. API is versioned under /api/v1/.

**No Django admin.** It was scaffolded in It.0 and never revisited, and It.8 proved what it cost:
a staff account could hard-DELETE a `Document` row through it — gone from `all_objects`, the
manager that is supposed to see everything — with **zero** audit rows written, and edit any case
outside the service layer, so no optimistic lock and no before/after trail. That defeats the two
invariants this system is built on (§11.1, §11.2) from inside the boundary that is supposed to
enforce them. Nothing needed it: the app has its own admin screens, including the restore desk
for soft-deleted rows (UC-063) and the audit trail (§11.3).
"""

from pathlib import Path

from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from accounts.views import AssignableLawyersView, UserViewSet
from catalog.views import (
    CategoryViewSet,
    DocumentTypesView,
    InstitutesView,
    TemplateTypesView,
)
from common.version import APP_VERSION, BUILD_NUMBER
from common.views import ActivityLogViewSet, ActivityVocabularyView
from clients.views import ClientViewSet
from documents.views import DocumentTemplateViewSet, DocumentViewSet, GenerationJobViewSet
from ocr.views import CardScanViewSet
from processes.views import InstituteEntryViewSet, ProcessViewSet
from reports.views import DashboardView, ProcessReportView, UserReportView


def health(_request):
    """Readiness: can this instance actually serve? (§4.2, §13.3)

    It answered a static `{"status": "ok"}` until It.9 — true the moment Django started, and
    therefore useless to a Compose healthcheck or a restore drill. **A health endpoint that
    cannot fail is worse than none**, because it is trusted. Each dependency is checked for real:

    * **database** — a trivial query, which is what proves a restore actually landed;
    * **redis** — Celery's broker. Without it a generation or an OCR read is accepted and then
      never runs, which the user experiences as a job stuck for ever (§6.3);
    * **documents** — the bind-mounted store (§2.5). Present *and writable*: a read-only or
      unmounted data root fails at the first upload, not at start-up.

    Returns **503** when anything is down, so `depends_on: condition: service_healthy` and any
    monitoring can act on it. Still unauthenticated — it exposes nothing a caller could not learn
    by trying the app, and a probe that needs a token is a probe that stops working when auth does.

    It carries the build because the frontend's mismatch check and a support call both need to
    ask the *server* what it is running; `app_version`/`build`, never `version`, which is the
    optimistic-lock counter everywhere else in this API.
    """
    checks: dict[str, str] = {}

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {type(exc).__name__}"

    try:
        from kombu import Connection

        with Connection(settings.CELERY_BROKER_URL) as broker:
            broker.ensure_connection(max_retries=0, timeout=2)
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"error: {type(exc).__name__}"

    try:
        root = Path(settings.DOCUMENTS_ROOT)
        root.mkdir(parents=True, exist_ok=True)
        # Written, not just stat'd: a bind mount can be present and read-only, and the office's
        # whole archive lives here.
        probe = root / ".health-write-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        checks["documents"] = "ok"
    except Exception as exc:
        checks["documents"] = f"error: {type(exc).__name__}"

    healthy = all(value == "ok" for value in checks.values())
    return JsonResponse(
        {
            "status": "ok" if healthy else "degraded",
            "checks": checks,
            "app_version": APP_VERSION,
            "build": BUILD_NUMBER,
        },
        status=200 if healthy else 503,
    )


router = DefaultRouter()
router.register("users", UserViewSet, basename="user")
router.register("categories", CategoryViewSet, basename="category")
router.register("clients", ClientViewSet, basename="client")
router.register("processes", ProcessViewSet, basename="process")
router.register("institute-entries", InstituteEntryViewSet, basename="institute-entry")
router.register("documents", DocumentViewSet, basename="document")
router.register("document-templates", DocumentTemplateViewSet, basename="document-template")
router.register("generation-jobs", GenerationJobViewSet, basename="generation-job")
router.register("activities", ActivityLogViewSet, basename="activity")
router.register("card-scans", CardScanViewSet, basename="card-scan")

urlpatterns = [
    path("api/v1/health/", health, name="health"),
    path("api/v1/auth/", include("accounts.urls")),
    path("api/v1/institutes/", InstitutesView.as_view(), name="institutes"),
    path("api/v1/document-types/", DocumentTypesView.as_view(), name="document-types"),
    path("api/v1/template-types/", TemplateTypesView.as_view(), name="template-types"),
    path("api/v1/lawyers/", AssignableLawyersView.as_view(), name="lawyers"),
    path("api/v1/activity-vocabulary/", ActivityVocabularyView.as_view(), name="activity-vocabulary"),
    path("api/v1/dashboard/", DashboardView.as_view(), name="dashboard"),
    path("api/v1/reports/processes/", ProcessReportView.as_view(), name="report-processes"),
    path("api/v1/reports/users/", UserReportView.as_view(), name="report-users"),
    path("api/v1/", include(router.urls)),
]
