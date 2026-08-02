"""Clients API — read + update, and the pre-save duplicate check (§4, §5.7).

**No create, no delete** (It.7, UC-026): a beneficiary comes into existence only through the Step-1
intake form, which builds them through `intake_process`/`confirm_scan` — the *services*, not this
endpoint. The Clients screen is for finding someone, so `POST` and `DELETE` are **405**, composed
away by the mixins below rather than merely hidden in the UI (§7.2).

`PATCH` stays: Step 1 edits the beneficiary through it, and since UC-030 that is the only screen
that can fill their place of birth, address and phone.
"""

from rest_framework import mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from common.viewsets import AuditedSoftDeleteViewSet
from documents.refile import refile_client_documents
from processes.services import recompute_client_state

from .permissions import IsClientEditorOrAdmin
from .selectors import duplicate_matches, search_clients
from .serializers import ClientSerializer, DuplicateCheckSerializer


class ClientViewSet(
    AuditedSoftDeleteViewSet,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    GenericViewSet,
):
    serializer_class = ClientSerializer
    permission_classes = (IsClientEditorOrAdmin,)
    audit_entity = "Client"

    def get_queryset(self):
        return search_clients(
            search=self.request.query_params.get("search", ""),
            pid=self.request.query_params.get("pid", ""),
        )

    def perform_update(self, serializer):
        super().perform_update(serializer)
        # Marital status decides whether Step 1 owes a spouse ID, so the stored step status has
        # to be re-derived here or the badge keeps claiming complete (§3.6). Editing `spouse_pid`
        # (or clearing it on a divorce) likewise changes the household duplicate rule (§5.7).
        recompute_client_state(serializer.instance)
        # The store path is composed from the category and PID, and the download name from the
        # person's name — correcting any of them makes the stored path a lie (§6.7).
        refile_client_documents(
            serializer.instance, actor=self.request.user, request=self.request
        )

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
