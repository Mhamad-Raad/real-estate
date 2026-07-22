"""Auth endpoints: login / refresh / logout / me. Login and logout are audited (§7, §11)."""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from common.models import ActivityLog
from common.services import record_activity

from .serializers import LoginSerializer, UserPreferencesSerializer, UserSerializer


class LoginView(TokenObtainPairView):
    """Issue tokens + user profile; records a login audit row on success."""

    serializer_class = LoginSerializer

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == status.HTTP_200_OK:
            user = response.data.get("user", {})
            record_activity(
                actor=None,
                action=ActivityLog.Action.LOGIN,
                entity_type="User",
                entity_id=user.get("id", ""),
                request=request,
                after={"username": user.get("username")},
            )
        return response


class LogoutView(APIView):
    """Blacklist the supplied refresh token and record a logout audit row."""

    permission_classes = (IsAuthenticated,)

    def post(self, request):
        refresh = request.data.get("refresh")
        if not refresh:
            return Response(
                {"detail": "refresh token required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            RefreshToken(refresh).blacklist()
        except TokenError:
            return Response(
                {"detail": "invalid or expired token"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        record_activity(
            actor=request.user,
            action=ActivityLog.Action.LOGOUT,
            entity_type="User",
            entity_id=request.user.id,
            request=request,
        )
        return Response(status=status.HTTP_205_RESET_CONTENT)


class MeView(APIView):
    """Read or update the current user's own profile (UI preferences only)."""

    permission_classes = (IsAuthenticated,)

    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        serializer = UserPreferencesSerializer(
            request.user, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserSerializer(request.user).data)
