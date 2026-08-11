"""Auth endpoints: login / refresh / logout / me. Login and logout are audited (§7, §11)."""

from django.db import transaction
from django.shortcuts import get_object_or_404
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
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.views import TokenObtainPairView

from common.models import ActivityLog
from common.permissions import IsAdmin
from common.services import record_activity
from common.viewsets import AuditedSoftDeleteViewSet

from .models import User
from .selectors import assignable_lawyers
from .serializers import AdminUserSerializer, LoginSerializer, UserSerializer


class LoginThrottle(ScopedRateThrottle):
    """Rate-limit sign-in attempts by IP (§12).

    **Counts failures only.** A throttle that also counted successes would lock out the shared
    office computer that several lawyers sign in from during a shift — the two computers are used
    by the whole office, so per-IP is per-*desk*, not per-person. A correct password is evidence
    of a legitimate user, so only rejections consume the allowance.
    """

    scope = "login"

    def throttle_success(self):
        """A successful *request* is not a failed *login*, so the normal path records nothing.

        DRF charges the allowance here, on every request that passes the check. Overriding it to
        do nothing moves the decision to the view, which is the only place that knows whether the
        credentials were actually right.
        """
        return True

    def record_failure(self, request, view):
        """Charge one failed attempt.

        `allow_request` is re-run first because DRF hands the view a **fresh** throttle instance:
        the one that ran during `check_throttles` is gone, and without its `history` loaded there
        is nothing to append to. It records nothing itself — `throttle_success` above is a no-op —
        so this re-check is free.
        """
        super().allow_request(request, view)
        super().throttle_success()


class LoginView(TokenObtainPairView):
    """Issue tokens + user profile; records a login audit row on success."""

    serializer_class = LoginSerializer
    throttle_classes = (LoginThrottle,)
    throttle_scope = "login"

    def post(self, request, *args, **kwargs):
        try:
            response = super().post(request, *args, **kwargs)
        except Exception:
            self._count_failure(request)
            raise
        if response.status_code != status.HTTP_200_OK:
            self._count_failure(request)
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

    def _count_failure(self, request):
        """Charge a failed attempt against the throttle. A wrong password raises from the
        serializer, so this runs on the exception path as well as a plain non-200."""
        for throttle in self.get_throttles():
            if isinstance(throttle, LoginThrottle):
                throttle.record_failure(request, self)


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


class AssignableLawyersView(APIView):
    """Minimal id+username list of active users for per-institute assignment dropdowns (§5.1).

    Read-only and available to any authenticated user (the full Users admin API stays admin-only)."""

    permission_classes = (IsAuthenticated,)

    def get(self, request):
        return Response(list(assignable_lawyers().values("id", "username")))


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
        # 404 rather than the `DoesNotExist` 500 an unknown id used to raise (It.8).
        instance = get_object_or_404(User.all_objects, pk=pk)
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
