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

from .models import User
from .serializers import LoginSerializer, UserSerializer


class LoginView(TokenObtainPairView):
    """Issue tokens + user profile; records a login audit row on success."""

    serializer_class = LoginSerializer

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == status.HTTP_200_OK:
            user = response.data.get("user", {})
            # Attribute the row to the user who just authenticated (request.user is anonymous here).
            actor = User.objects.filter(pk=user.get("id")).first()
            record_activity(
                actor=actor,
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
    """Read the current user's own profile."""

    permission_classes = (IsAuthenticated,)

    def get(self, request):
        return Response(UserSerializer(request.user).data)
