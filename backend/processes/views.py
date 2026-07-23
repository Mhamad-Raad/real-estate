"""Processes API — create (sets process-wide lawyer), search list, header edit, override (§4, §7)."""

from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from common.permissions import IsAdmin, IsProcessAssigneeOrAdmin
from common.viewsets import AuditedSoftDeleteViewSet

from .selectors import search_processes
from .serializers import (
    OverrideSerializer,
    ProcessCreateSerializer,
    ProcessDetailSerializer,
    ProcessListSerializer,
    ProcessUpdateSerializer,
)
from .services import create_process, override_duplicate

SERIALIZERS = {
    "list": ProcessListSerializer,
    "retrieve": ProcessDetailSerializer,
    "create": ProcessCreateSerializer,
    "update": ProcessUpdateSerializer,
    "partial_update": ProcessUpdateSerializer,
}


class ProcessViewSet(AuditedSoftDeleteViewSet, ModelViewSet):
    permission_classes = (IsProcessAssigneeOrAdmin,)
    audit_entity = "Process"

    def get_queryset(self):
        return search_processes(self.request.query_params)

    def get_serializer_class(self):
        return SERIALIZERS.get(self.action, ProcessDetailSerializer)

    def perform_create(self, serializer):
        data = serializer.validated_data
        user = self.request.user
        # Lawyers may only assign themselves; admins may assign anyone (field-level, §7.2).
        assigned = data.get("assigned_lawyer") or user
        if not user.is_admin:
            assigned = user
        serializer.instance = create_process(
            client=data["client"],
            assigned_lawyer=assigned,
            actor=user,
            parcel=data.get("parcel"),
            category=data.get("category"),
            request=self.request,
        )

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[IsAdmin],
        url_path="override-duplicate",
    )
    def override_duplicate(self, request, pk=None):
        """Admin-only: clear a fired duplicate warning with a mandatory reason (§5.7)."""
        process = self.get_object()
        payload = OverrideSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        override_duplicate(
            process=process,
            admin=request.user,
            match_reason=payload.validated_data["match_reason"],
            reason=payload.validated_data["reason"],
            expected_version=payload.validated_data.get("version"),
            request=request,
        )
        process.refresh_from_db()
        return Response(ProcessDetailSerializer(process).data)
