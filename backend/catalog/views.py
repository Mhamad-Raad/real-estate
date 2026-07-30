"""Category CRUD (admin-write, all-read) and the read-only institutes enum (§3.4, §4)."""

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from common.permissions import IsAdminOrReadOnly
from common.viewsets import AuditedSoftDeleteViewSet

from .document_types import document_types_as_dicts
from .institutes import institutes_as_dicts
from .models import Category
from .serializers import CategorySerializer


class CategoryViewSet(AuditedSoftDeleteViewSet, ModelViewSet):
    queryset = Category.objects.all().order_by("code")
    serializer_class = CategorySerializer
    permission_classes = (IsAdminOrReadOnly,)
    audit_entity = "Category"
    # A category classifies cases and names their folder on disk (§6.7), so it may not be removed
    # while any live case or beneficiary still belongs to it.
    protect_if_used = ("processes", "clients")


class InstitutesView(APIView):
    """The shared Step 2–4 institute enum — read-only single source of truth."""

    permission_classes = (IsAuthenticated,)

    def get(self, _request):
        return Response(institutes_as_dicts())


class DocumentTypesView(APIView):
    """The shared controlled document-type vocabulary — read-only single source of truth (§6.7)."""

    permission_classes = (IsAuthenticated,)

    def get(self, _request):
        return Response(document_types_as_dicts())
