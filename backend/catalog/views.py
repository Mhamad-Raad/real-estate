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
    # Served whole, like the other controlled vocabularies: this list is a handful of rows and it
    # fills five dropdowns, each of which silently lost everything past page 1 while it was paged.
    pagination_class = None
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


class TemplateTypesView(APIView):
    """The template types the backend actually supports — read-only (§6.6, UC-008).

    Served rather than hard-coded because the frontend kept its own copy in three places and fell
    a whole type behind when `case_summary` was added in It.4: the compiled-case cover sheet could
    not be chosen at all, and its label rendered as the raw i18n key. Same shape as
    `/institutes/` — machine `code` plus an i18n `display_key`, so labels stay translatable.

    Deliberately only those two: whether a type is a blank form is carried by each template row
    (`is_blank_form`), which is the object every screen actually holds. Answering it here as well
    would give one fact two homes, and the screen would read it from whichever request landed.
    """

    permission_classes = (IsAuthenticated,)

    def get(self, _request):
        from documents.models import DocumentTemplate

        return Response(
            [
                {"code": value, "display_key": f"templates.types.{value}"}
                for value in DocumentTemplate.TemplateType.values
            ]
        )
