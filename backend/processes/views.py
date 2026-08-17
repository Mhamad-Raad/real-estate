"""Processes API — create, search, header edit, override, per-step save, complete (§4, §5, §7)."""

from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from common.permissions import IsAdmin, IsProcessAssigneeOrAdmin
from common.viewsets import AuditedSoftDeleteViewSet
from documents.compile import start_compile_case_job
from documents.generation import (
    start_eligibility_job,
    start_process_codes_job,
    start_process_list_job,
)
from documents.serializers import GenerationJobSerializer

from .constants import FIRST_STEP, LAST_STEP
from .models import Process, ProcessInstituteEntry
from .permissions import IsEntryEditorOrAdmin
from .selectors import search_processes
from .serializers import (
    GenerateDocumentSerializer,
    InstituteEntrySerializer,
    OverrideSerializer,
    ProcessCreateSerializer,
    ProcessDetailSerializer,
    ProcessListSerializer,
    ProcessStepSerializer,
    ProcessUpdateSerializer,
    ReassignSerializer,
)
# Services that share a name with the view action below are aliased, so a stray `self.` can never
# turn a service call into silent recursion.
from .services import (
    advance_step as advance_step_service,
    complete_process,
    intake_process,
    override_duplicate as override_duplicate_service,
    reassign_process,
    recompute_step,
    release_client_with_case,
    restore_client_with_case,
    save_step,
    settle_entry,
)

SERIALIZERS = {
    "list": ProcessListSerializer,
    # The restore desk lists cases, not full case files (UC-063).
    "deleted": ProcessListSerializer,
    "retrieve": ProcessDetailSerializer,
    "create": ProcessCreateSerializer,
    "update": ProcessUpdateSerializer,
    "partial_update": ProcessUpdateSerializer,
}


class ProcessViewSet(AuditedSoftDeleteViewSet, ModelViewSet):
    permission_classes = (IsProcessAssigneeOrAdmin,)
    audit_entity = "Process"
    # The restore desk's listing reads both through the serializer (UC-063).
    deleted_select_related = ("client", "assigned_lawyer")

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
        # Any lawyer may open a case in a colleague's name — one person takes the papers in, another
        # works the case, and the office asked for that to be possible (2026-08-06). The field is
        # still an `AssignableLawyerField`, so the name has to belong to someone active and not
        # deleted (§7.2 layer 6); it is *who* may be named that is open, never *whether they exist*.
        # Defaults to the caller when nothing is named, which is the common case.
        assigned = data.get("assigned_lawyer") or user
        serializer.instance = intake_process(
            client=data.get("client"),
            client_data=data.get("client_data"),
            assigned_lawyer=assigned,
            actor=user,
            category=data.get("category"),
            land_id=data.get("land_id", ""),
            land_address=data.get("land_address", ""),
            request=self.request,
        )

    def after_soft_delete(self, instance):
        """Deleting the case releases the beneficiary too, so they can be entered again (UC-061).

        A hook rather than an overridden `perform_destroy`/`restore` pair: the base already runs
        both inside a transaction, so re-declaring the action here only risked its `@action`
        config drifting out of step with the base's.
        """
        release_client_with_case(instance, actor=self.request.user, request=self.request)

    def after_restore(self, instance):
        """The mirror. If the beneficiary's national ID has been re-used since — a legitimate
        outcome of having freed it — this raises and the base's transaction rolls the case back
        with it, rather than handing back a case whose person is not in the register."""
        restore_client_with_case(instance, actor=self.request.user, request=self.request)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        # Both steps read header fields edited through here (Step 4 the `land_id`, UC-041), so
        # their stored status would otherwise go stale against the live rules (§3.6).
        recompute_step(serializer.instance, 1)
        recompute_step(serializer.instance, 4)
        # No refile here: the store path is composed from the category, the case number and the
        # PID (§6.7), and none of the three can change through this endpoint — the category is
        # fixed for the life of the case (UC-059), the number is system-owned and never editable
        # (UC-064), and the PID belongs to the client, which refiles on its own update.

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

    @action(detail=True, methods=["post"], permission_classes=[IsAdmin])
    def reassign(self, request, pk=None):
        """Admin-only: hand the case to a different lawyer (§7.2, 2026-08-06)."""
        process = self.get_object()
        payload = ReassignSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        process = reassign_process(
            process=process,
            new_lawyer=payload.validated_data["assigned_lawyer"],
            actor=request.user,
            expected_version=payload.validated_data.get("version"),
            request=request,
        )
        return Response(ProcessDetailSerializer(process).data)

    # Range built from the workflow's own bounds — a hand-written `[1-5]` here would keep
    # answering 404 for a step the rest of the system had already grown (§5, UC-043).
    @action(
        detail=True,
        methods=["get", "patch"],
        url_path=f"steps/(?P<n>[{FIRST_STEP}-{LAST_STEP}])",
    )
    def steps(self, request, pk=None, n=None):
        """GET a step's data + computed status, or PATCH it (save incomplete) — §5.2."""
        process = self.get_object()  # object permission: read=all, write=assignee/admin
        step_number = int(n)
        step_row = process.steps.get(step_number=step_number)
        if request.method == "GET":
            return Response(ProcessStepSerializer(step_row).data)
        # Deserialize before writing. The service assigns these straight onto the model, so an
        # unparseable date (`"not-a-date"`) used to reach `save()` and surface as a **500**;
        # through the serializer it is a 400 naming the field, like every other bad input.
        payload = ProcessStepSerializer(step_row, data=request.data, partial=True)
        payload.is_valid(raise_exception=True)
        step = save_step(
            process=process,
            step_number=step_number,
            data=payload.validated_data,
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

    @action(detail=True, methods=["post"], url_path="generate-eligibility")
    def generate_eligibility(self, request, pk=None):
        """Queue the beneficiary's letter (§6.6). Generation is a *result* of finishing Step 1,
        never a requirement of it — requiring it would deadlock the step it depends on (§0)."""
        process = self.get_object()  # write action: assignee or admin only
        job = start_eligibility_job(
            process=process,
            actor=request.user,
            template_id=request.data.get("template"),
            request=request,
        )
        return Response(GenerationJobSerializer(job).data, status=status.HTTP_202_ACCEPTED)

    @action(detail=False, methods=["post"], url_path="generate-codes")
    def generate_codes(self, request):
        """Queue the office's code list for the selected cases (§6.8, UC-057).

        A separate action rather than a mode of `generate-document`: it binds to a different
        template with different columns, and it carries a step gate the list letter does not.
        Like the list letter it only exports rows the caller can already see, so it stays open to
        any authenticated user and files nothing onto a case.
        """
        payload = GenerateDocumentSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        job = start_process_codes_job(
            process_ids=payload.validated_data["process_ids"],
            actor=request.user,
            template_id=payload.validated_data.get("template"),
            request=request,
        )
        return Response(GenerationJobSerializer(job).data, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["post"], url_path="compile")
    def compile_case(self, request, pk=None):
        """Queue the Step-5 compiled export: summary cover sheet + every document (§10.3)."""
        process = self.get_object()  # write action: assignee or admin only
        job = start_compile_case_job(
            process=process,
            actor=request.user,
            template_id=request.data.get("template"),
            request=request,
        )
        return Response(GenerationJobSerializer(job).data, status=status.HTTP_202_ACCEPTED)

    @action(detail=False, methods=["post"], url_path="generate-document")
    def generate_document(self, request):
        """Queue the letter the selection calls for (§6.8, UC-016).

        One case selected means the office wants *that person's* eligibility letter, not a
        one-row list. Delegating to the existing eligibility job keeps a single code path per
        output kind — and files the letter on the case, superseding the previous copy, exactly as
        Step 1's own button does.
        """
        payload = GenerateDocumentSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        process_ids = payload.validated_data["process_ids"]
        template_id = payload.validated_data.get("template")

        if len(process_ids) == 1:
            process = get_object_or_404(Process, pk=process_ids[0])
            # The list letter only exports rows the caller can already see, so it stays open to
            # any authenticated user. This branch *writes* a Document onto the case, and a write
            # follows that case's assignment like every other write (§7.2).
            if not (request.user.is_admin or process.assigned_lawyer_id == request.user.id):
                raise PermissionDenied("Only the assigned lawyer or an admin may file this letter.")
            job = start_eligibility_job(
                process=process, actor=request.user, template_id=template_id, request=request
            )
        else:
            job = start_process_list_job(
                process_ids=process_ids,
                actor=request.user,
                template_id=template_id,
                request=request,
            )
        return Response(GenerationJobSerializer(job).data, status=status.HTTP_202_ACCEPTED)


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
        settle_entry(entry)
