"""Root URL config. API is versioned under /api/v1/."""

from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def health(_request):
    return JsonResponse({"status": "ok"})

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/health/", health, name="health"),
    path("api/v1/auth/", include("accounts.urls")),
]
