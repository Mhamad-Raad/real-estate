"""Clients API — CRUD + the pre-save duplicate check (§4, §5.7)."""

from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from common.viewsets import AuditedSoftDeleteViewSet
from processes.services import recompute_client_steps, recompute_duplicate_flags

from .permissions import IsClientEditorOrAdmin
from .selectors import duplicate_matches, search_clients
from .serializers import ClientSerializer, DuplicateCheckSerializer
from .services import create_client


class ClientViewSet(AuditedSoftDeleteViewSet, ModelViewSet):
    serializer_class = ClientSerializer
    permission_classes = (IsClientEditorOrAdmin,)
    audit_entity = "Client"

    def get_queryset(self):
        return search_clients(
            search=self.request.query_params.get("search", ""),
            pid=self.request.query_params.get("pid", ""),
        )

    def perform_create(self, serializer):
        # Route creation through the service so audit stays single-sourced.
        serializer.instance = create_client(
            data=serializer.validated_data, actor=self.request.user, request=self.request
        )

    def perform_update(self, serializer):
        super().perform_update(serializer)
        # Marital status decides whether Step 1 owes a spouse ID, so the stored step status has
        # to be re-derived here or the badge keeps claiming complete (§3.6). Editing `spouse_pid`
        # (or clearing it on a divorce) likewise changes the household duplicate rule (§5.7).
        recompute_duplicate_flags(serializer.instance)
        recompute_client_steps(serializer.instance)

    @action(detail=False, methods=["post"], url_path="duplicate-check")
    def duplicate_check(self, request):
        """Return PID/household matches and mother-name (fuzzy) matches before a client is saved."""
        payload = DuplicateCheckSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        report = duplicate_matches(
            pid=payload.validated_data.get("pid", ""),
            mother_full_name=payload.validated_data.get("mother_full_name", ""),
            spouse_pid=payload.validated_data.get("spouse_pid", ""),
            exclude_id=payload.validated_data.get("exclude_id"),
        )
        return Response(
            {
                "pid_matches": ClientSerializer(report.pid, many=True).data,
                # Kept separate from `pid_matches`: both block, but telling a lawyer "same
                # National ID" about their applicant's spouse would simply be untrue.
                "household_matches": ClientSerializer(report.household, many=True).data,
                "mother_name_matches": ClientSerializer(report.mother_name, many=True).data,
            }
        )
