"""Shared CRUD base: soft-delete, optimistic locking, and audit for simple resources.

Complex domain operations (create_process, override_duplicate…) still go through each app's
services.py; this base only centralizes the mechanical CRUD audit + soft-delete + version bump.
"""

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .locking import check_version
from .models import ActivityLog
from .permissions import IsAdmin
from .services import record_activity


class AuditedSoftDeleteViewSet:
    """Mixin for DRF ModelViewSets — override `audit_entity` with the model name."""

    audit_entity = "Entity"
    # Reverse accessors that must hold no live rows before this resource may be soft-deleted.
    #
    # `on_delete=PROTECT` cannot cover this: a soft-delete issues no SQL DELETE, so the database
    # never gets the chance to refuse it and every FK guard is bypassed. Without this list, a
    # category still carrying live cases disappears from every dropdown, filter and report while
    # the cases keep pointing at it — the records look intact but can no longer be grouped by
    # the thing that classifies them.
    protect_if_used: tuple[str, ...] = ()

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

    def assert_not_in_use(self, instance):
        """Refuse the delete while live records still reference this one.

        Counted through the reverse accessors, which use the related model's default manager and
        therefore see **live rows only** — a category whose only cases were themselves deleted is
        free to go.
        """
        blocking = {
            relation: count
            for relation in self.protect_if_used
            if (count := getattr(instance, relation).count())
        }
        if blocking:
            raise ValidationError(
                {
                    "detail": "This record is still in use and cannot be deleted.",
                    "in_use": blocking,
                }
            )

    @transaction.atomic
    def perform_destroy(self, instance):
        self.assert_not_in_use(instance)
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
