"""Land parcels API — CRUD (shared reference data; any authenticated user)."""

from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from common.viewsets import AuditedSoftDeleteViewSet

from .models import LandParcel
from .serializers import LandParcelSerializer


class LandParcelViewSet(AuditedSoftDeleteViewSet, ModelViewSet):
    queryset = LandParcel.objects.all().order_by("parcel_number")
    serializer_class = LandParcelSerializer
    permission_classes = (IsAuthenticated,)
    audit_entity = "LandParcel"
