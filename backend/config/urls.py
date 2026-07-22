"""Root URL config. API is versioned under /api/v1/."""

from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from catalog.views import CategoryViewSet, InstitutesView
from clients.views import ClientViewSet
from parcels.views import LandParcelViewSet
from processes.views import ProcessViewSet


def health(_request):
    return JsonResponse({"status": "ok"})


router = DefaultRouter()
router.register("categories", CategoryViewSet, basename="category")
router.register("clients", ClientViewSet, basename="client")
router.register("parcels", LandParcelViewSet, basename="parcel")
router.register("processes", ProcessViewSet, basename="process")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/health/", health, name="health"),
    path("api/v1/auth/", include("accounts.urls")),
    path("api/v1/institutes/", InstitutesView.as_view(), name="institutes"),
    path("api/v1/", include(router.urls)),
]
