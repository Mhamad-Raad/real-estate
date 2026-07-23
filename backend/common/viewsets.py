"""Shared CRUD base: soft-delete, optimistic locking, and audit for simple resources.

Complex domain operations (create_process, override_duplicate…) still go through each app's
services.py; this base only centralizes the mechanical CRUD audit + soft-delete + version bump.
"""

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from .locking import check_version
from .models import ActivityLog
from .permissions import IsAdmin
from .services import record_activity


class AuditedSoftDeleteViewSet:
    """Mixin for DRF ModelViewSets — override `audit_entity` with the model name."""

    audit_entity = "Entity"

    @transaction.atomic  # mutation + its audit row commit together or not at all (§11)
    def perform_create(self, serializer):
        obj = serializer.save()
        record_activity(
            actor=self.request.user,
            action=ActivityLog.Action.CREATE,
            entity_type=self.audit_entity,
            entity_id=obj.pk,
            after=self.get_serializer(obj).data,
            request=self.request,
        )

    @transaction.atomic
    def perform_update(self, serializer):
        instance = serializer.instance
        # Optimistic lock: version is mandatory on updates and must still match (else 409).
        check_version(instance, self.request.data.get("version"), required=True)
        before = self.get_serializer(instance).data
        obj = serializer.save(version=instance.version + 1)
        record_activity(
            actor=self.request.user,
            action=ActivityLog.Action.UPDATE,
            entity_type=self.audit_entity,
            entity_id=obj.pk,
            before=before,
            after=self.get_serializer(obj).data,
            request=self.request,
        )

    @transaction.atomic
    def perform_destroy(self, instance):
        # Soft-delete only — never a hard DELETE.
        instance.is_deleted = True
        instance.deleted_at = timezone.now()
        instance.deleted_by = self.request.user
        instance.version += 1
        instance.save(update_fields=["is_deleted", "deleted_at", "deleted_by", "version"])
        record_activity(
            actor=self.request.user,
            action=ActivityLog.Action.DELETE,
            entity_type=self.audit_entity,
            entity_id=instance.pk,
            request=self.request,
        )

    @action(detail=True, methods=["post"], permission_classes=[IsAdmin])
    @transaction.atomic
    def restore(self, request, pk=None):
        """Admin-only: reverse a soft-delete."""
        instance = self.get_queryset().model.all_objects.get(pk=pk)
        instance.is_deleted = False
        instance.deleted_at = None
        instance.deleted_by = None
        instance.version += 1
        instance.save(update_fields=["is_deleted", "deleted_at", "deleted_by", "version"])
        record_activity(
            actor=request.user,
            action=ActivityLog.Action.RESTORE,
            entity_type=self.audit_entity,
            entity_id=instance.pk,
            request=request,
        )
        return Response(self.get_serializer(instance).data, status=status.HTTP_200_OK)
