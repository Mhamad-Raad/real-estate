"""Auth routes under /api/v1/auth/."""

from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import LoginView, LogoutView, MeView

urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", MeView.as_view(), name="me"),
]
