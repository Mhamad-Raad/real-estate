"""Documents API — upload (multipart), metadata, permission-checked download, soft-delete (§4.4)."""

from django.conf import settings
from django.http import FileResponse, Http404
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from common.viewsets import AuditedSoftDeleteViewSet
from processes.services import recompute_step

from .models import Document
from .permissions import IsDocumentEditorOrAdmin
from .selectors import documents_for_process
from .serializers import DocumentSerializer, DocumentUploadSerializer
from .services import create_document


class DocumentViewSet(AuditedSoftDeleteViewSet, ModelViewSet):
    serializer_class = DocumentSerializer
    permission_classes = (IsDocumentEditorOrAdmin,)
    parser_classes = (MultiPartParser, FormParser)
    audit_entity = "Document"
    http_method_names = ["get", "post", "delete"]  # no PATCH — documents are immutable once stored

    def get_queryset(self):
        qs = Document.objects.select_related("process", "institute_entry").order_by("-created_at")
        process_id = self.request.query_params.get("process")
        return documents_for_process(process_id) if process_id else qs

    def create(self, request, *args, **kwargs):
        payload = DocumentUploadSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        process = data["process"]
        # Upload is a write — only the process assignee or an admin may attach documents.
        if not (request.user.is_admin or process.assigned_lawyer_id == request.user.id):
            raise PermissionDenied("Only the assigned lawyer or an admin can add documents.")
        upload = data["file"]
        document = create_document(
            process=process,
            step_number=data["step_number"],
            document_type=data["document_type"],
            input_source=data["input_source"],
            institute_entry=data.get("institute_entry"),
            content=upload.read(),
            original_filename=getattr(upload, "name", ""),
            actor=request.user,
            request=request,
        )
        # A new document may complete its step — re-derive the step status (§3.6).
        recompute_step(process, document.step_number)
        return Response(DocumentSerializer(document).data, status=status.HTTP_201_CREATED)

    def perform_destroy(self, instance):
        process, step_number = instance.process, instance.step_number
        super().perform_destroy(instance)
        recompute_step(process, step_number)

    @action(detail=True, methods=["get"])
    def file(self, request, pk=None):
        """Stream the PDF bytes with the friendly display name — never served statically (§4.4)."""
        document = self.get_object()  # runs object permission (read allowed to any authed user)
        path = settings.DOCUMENTS_ROOT / document.file_path
        if not path.exists():
            raise Http404("File is missing from the store.")
        return FileResponse(
            open(path, "rb"),
            as_attachment=True,
            filename=document.display_filename,
            content_type="application/pdf",
        )
