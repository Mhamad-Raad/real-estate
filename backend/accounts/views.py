"""Auth endpoints: login / refresh / logout / me. Login and logout are audited (§7, §11)."""

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from common.models import ActivityLog
from common.permissions import IsAdmin
from common.services import record_activity
from common.viewsets import AuditedSoftDeleteViewSet

from .models import User
from .serializers import AdminUserSerializer, LoginSerializer, UserSerializer


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


class UserViewSet(AuditedSoftDeleteViewSet, ModelViewSet):
    """Admin-only user management: CRUD + soft-delete/restore, all audited (§4, §7, §11)."""

    serializer_class = AdminUserSerializer
    permission_classes = (IsAdmin,)
    audit_entity = "User"

    def get_queryset(self):
        return User.objects.filter(is_deleted=False).order_by("username")

    def perform_update(self, serializer):
        # Never let an edit strip the system of its last usable admin (role change or deactivation).
        self._guard_last_admin(serializer.instance, serializer.validated_data)
        super().perform_update(serializer)

    def _guard_last_admin(self, instance, data):
        was_admin = instance.role == User.Role.ADMIN and instance.is_active and not instance.is_deleted
        stays_admin = (
            data.get("role", instance.role) == User.Role.ADMIN
            and data.get("is_active", instance.is_active)
        )
        if was_admin and not stays_admin:
            other_admin_exists = (
                User.objects.filter(is_deleted=False, is_active=True, role=User.Role.ADMIN)
                .exclude(pk=instance.pk)
                .exists()
            )
            if not other_admin_exists:
                raise ValidationError(
                    {"detail": "At least one active administrator must remain."}
                )

    @transaction.atomic
    def perform_destroy(self, instance):
        # Guard: an admin can't lock themselves out by deleting their own account.
        if instance.id == self.request.user.id:
            raise ValidationError({"detail": "You cannot delete your own account."})
        # Soft-delete AND deactivate so the account can no longer authenticate.
        instance.is_active = False
        instance.is_deleted = True
        instance.deleted_at = timezone.now()
        instance.deleted_by = self.request.user
        instance.version += 1
        instance.save(
            update_fields=["is_active", "is_deleted", "deleted_at", "deleted_by", "version"]
        )
        record_activity(
            actor=self.request.user,
            action=ActivityLog.Action.DELETE,
            entity_type="User",
            entity_id=instance.pk,
            request=self.request,
        )

    @action(detail=True, methods=["post"], permission_classes=[IsAdmin])
    @transaction.atomic
    def restore(self, request, pk=None):
        # Re-enable login on restore (mirrors the deactivation done on delete).
        instance = User.all_objects.get(pk=pk)
        instance.is_active = True
        instance.is_deleted = False
        instance.deleted_at = None
        instance.deleted_by = None
        instance.version += 1
        instance.save(
            update_fields=["is_active", "is_deleted", "deleted_at", "deleted_by", "version"]
        )
        record_activity(
            actor=request.user,
            action=ActivityLog.Action.RESTORE,
            entity_type="User",
            entity_id=instance.pk,
            request=request,
        )
        return Response(self.get_serializer(instance).data, status=status.HTTP_200_OK)
