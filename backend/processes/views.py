"""Processes API — create, search, header edit, override, per-step save, complete (§4, §5, §7)."""

from django.db import IntegrityError
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from common.permissions import IsAdmin, IsProcessAssigneeOrAdmin
from common.viewsets import AuditedSoftDeleteViewSet

from .models import ProcessInstituteEntry
from .permissions import IsEntryEditorOrAdmin
from .selectors import search_processes
from .serializers import (
    InstituteEntrySerializer,
    OverrideSerializer,
    ProcessCreateSerializer,
    ProcessDetailSerializer,
    ProcessListSerializer,
    ProcessStepSerializer,
    ProcessUpdateSerializer,
)
# Services that share a name with the view action below are aliased, so a stray `self.` can never
# turn a service call into silent recursion.
from .services import (
    advance_step as advance_step_service,
    complete_process,
    create_process,
    override_duplicate as override_duplicate_service,
    recompute_step,
    save_step,
)

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
        qs = search_processes(self.request.query_params)
        if self.action == "retrieve":
            # The detail payload derives every step's `missing` list from these three collections;
            # prefetching turns five per-step round trips into one each (§3.6). Read-only action
            # only — a mutating request must not read through a stale prefetch cache.
            qs = qs.prefetch_related("steps", "documents", "institute_entries__documents")
        return qs

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
            category=data.get("category"),
            request=self.request,
        )

    def perform_update(self, serializer):
        super().perform_update(serializer)
        # Step 1's requirements include header fields (land_id, category) edited through here, so
        # its stored status would otherwise go stale against the live requirement list (§3.6).
        recompute_step(serializer.instance, 1)

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
        override_duplicate_service(
            process=process,
            admin=request.user,
            match_reason=payload.validated_data["match_reason"],
            reason=payload.validated_data["reason"],
            expected_version=payload.validated_data.get("version"),
            request=request,
        )
        process.refresh_from_db()
        return Response(ProcessDetailSerializer(process).data)

    @action(detail=True, methods=["get", "patch"], url_path="steps/(?P<n>[1-5])")
    def steps(self, request, pk=None, n=None):
        """GET a step's data + computed status, or PATCH it (save incomplete) — §5.2."""
        process = self.get_object()  # object permission: read=all, write=assignee/admin
        step_number = int(n)
        if request.method == "GET":
            return Response(ProcessStepSerializer(process.steps.get(step_number=step_number)).data)
        step = save_step(
            process=process,
            step_number=step_number,
            data=request.data,
            actor=request.user,
            expected_version=request.data.get("version"),
            request=request,
        )
        return Response(ProcessStepSerializer(step).data)

    @action(detail=True, methods=["post"], url_path="advance-step")
    def advance_step(self, request, pk=None):
        """Unlock the next step for this case — the lawyer's explicit "proceed" (§5.2)."""
        process = self.get_object()  # write action: assignee or admin only
        process = advance_step_service(
            process=process,
            actor=request.user,
            expected_version=request.data.get("version"),
            request=request,
        )
        return Response(ProcessDetailSerializer(process).data)

    @action(detail=True, methods=["post"], url_path="steps/5/complete")
    def complete(self, request, pk=None):
        """Mark the case complete; blocks on missing files unless an admin forces it (§5, §10.3)."""
        process = self.get_object()
        force = bool(request.data.get("force"))
        if force and not request.user.is_admin:
            raise PermissionDenied("Only an admin can force completion past missing files.")
        process = complete_process(
            process=process,
            actor=request.user,
            force=force,
            expected_version=request.data.get("version"),
            request=request,
        )
        return Response(ProcessDetailSerializer(process).data)


class InstituteEntryViewSet(AuditedSoftDeleteViewSet, ModelViewSet):
    """Step 2–4 institute entries (§5.1). Any change re-derives the parent step's status."""

    serializer_class = InstituteEntrySerializer
    permission_classes = (IsEntryEditorOrAdmin,)
    audit_entity = "InstituteEntry"

    def get_queryset(self):
        qs = ProcessInstituteEntry.objects.select_related("process").order_by("step_number", "id")
        process_id = self.request.query_params.get("process")
        return qs.filter(process_id=process_id) if process_id else qs

    def perform_create(self, serializer):
        process = serializer.validated_data["process"]
        if not (self.request.user.is_admin or process.assigned_lawyer_id == self.request.user.id):
            raise PermissionDenied("Only the assigned lawyer or an admin can add institute entries.")
        try:
            super().perform_create(serializer)
        except IntegrityError:  # duplicate fixed institute for this process/step
            raise ValidationError(
                {"institute_code": "This institute is already recorded for this step."}
            )
        self._after_write(serializer.instance)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        self._after_write(serializer.instance)

    def perform_destroy(self, instance):
        process, step_number = instance.process, instance.step_number
        super().perform_destroy(instance)
        recompute_step(process, step_number)

    def _after_write(self, entry):
        # Step-2 approval auto-sets the step's end_date (editable later, §5.8).
        if entry.step_number == 2 and entry.approval_status != entry.ApprovalStatus.PENDING:
            step2 = entry.process.steps.get(step_number=2)
            if step2.end_date is None:
                step2.end_date = timezone.now().date()
                step2.save(update_fields=["end_date", "updated_at"])
        recompute_step(entry.process, entry.step_number)
