"""Audit-trail read endpoints (§11.3) — admin-only, and read-only by construction."""

from rest_framework.mixins import ListModelMixin, RetrieveModelMixin
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet

from .models import ActivityLog
from .permissions import IsAdmin
from .selectors import actors, entity_types, search_activities
from .serializers import ActivityLogSerializer


class ActivityLogViewSet(ListModelMixin, RetrieveModelMixin, GenericViewSet):
    """`GET /activities/` + `/activities/{id}/`.

    Deliberately only List and Retrieve: the trail is append-only, so there is no create,
    update or delete surface to expose — not even for an admin (§11.2).
    """

    serializer_class = ActivityLogSerializer
    permission_classes = (IsAdmin,)
    # Filtering lives in the selector, not django-filter, so the indexed contract is explicit.
    filter_backends = ()

    def get_queryset(self):
        return search_activities(self.request.query_params)


class ActivityVocabularyView(APIView):
    """The values the Activities filters offer, so the frontend hard-codes neither."""

    permission_classes = (IsAdmin,)

    def get(self, request):
        return Response(
            {
                "actions": [
                    {"value": value, "label": label} for value, label in ActivityLog.Action.choices
                ],
                "entity_types": entity_types(),
                "actors": actors(),
            }
        )
