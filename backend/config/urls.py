"""Root URL config. API is versioned under /api/v1/."""

from django.contrib import admin
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
from common.views import ActivityLogViewSet, ActivityVocabularyView
from clients.views import ClientViewSet
from documents.views import DocumentTemplateViewSet, DocumentViewSet, GenerationJobViewSet
from ocr.views import CardScanViewSet
from processes.views import InstituteEntryViewSet, ProcessViewSet
from reports.views import DashboardView, ProcessReportView, UserReportView


def health(_request):
    return JsonResponse({"status": "ok"})


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
    path("admin/", admin.site.urls),
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
