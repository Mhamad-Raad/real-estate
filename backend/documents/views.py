"""Documents API — upload (multipart), metadata, permission-checked download, soft-delete (§4.4)."""

from django.conf import settings
from django.http import FileResponse, Http404
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from common.permissions import IsAdminOrReadOnly
from common.viewsets import AuditedSoftDeleteViewSet
from processes.services import recompute_step

from .models import Document, DocumentTemplate, GenerationJob
from .permissions import IsDocumentEditorOrAdmin
from .selectors import documents_for_process
from .serializers import (
    DocumentSerializer,
    DocumentTemplateSerializer,
    DocumentTemplateUploadSerializer,
    DocumentUploadSerializer,
    GenerationJobSerializer,
)
from .services import create_document, create_template


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


class DocumentTemplateViewSet(AuditedSoftDeleteViewSet, ModelViewSet):
    """Admin-managed `.docx` letter templates (§6.6). Any authed user may read them (to pick one
    for a bulk letter); only an admin may upload, edit or remove."""

    serializer_class = DocumentTemplateSerializer
    permission_classes = (IsAdminOrReadOnly,)
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    audit_entity = "DocumentTemplate"

    def get_queryset(self):
        qs = DocumentTemplate.objects.select_related("uploaded_by").order_by("template_type")
        template_type = self.request.query_params.get("template_type")
        return qs.filter(template_type=template_type) if template_type else qs

    def perform_update(self, serializer):
        template = serializer.instance
        # "Active" is exclusive per type (partial-unique index): activating one retires the rest,
        # rather than letting the DB reject the write as a 500.
        if serializer.validated_data.get("is_active") and not template.is_active:
            DocumentTemplate.objects.filter(
                template_type=template.template_type, is_active=True
            ).exclude(pk=template.pk).update(is_active=False)
        super().perform_update(serializer)

    def create(self, request, *args, **kwargs):
        payload = DocumentTemplateUploadSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        template = create_template(
            template_type=payload.validated_data["template_type"],
            name=payload.validated_data["name"],
            upload=payload.validated_data["file"],
            actor=request.user,
            request=request,
        )
        return Response(DocumentTemplateSerializer(template).data, status=status.HTTP_201_CREATED)


class GenerationJobViewSet(ReadOnlyModelViewSet):
    """Poll a generation job and download a finished list letter (§6.6, §6.8)."""

    serializer_class = GenerationJobSerializer

    def get_queryset(self):
        qs = GenerationJob.objects.select_related("template", "process").order_by("-created_at")
        # A job exposes what its requester asked for, so only they (or an admin) may read it.
        return qs if self.request.user.is_admin else qs.filter(requested_by=self.request.user)

    @action(detail=True, methods=["get"])
    def file(self, request, pk=None):
        """Stream a finished list letter. Single-beneficiary letters are served as Documents."""
        job = self.get_object()
        if job.status != GenerationJob.Status.DONE or not job.output_path:
            raise Http404("This job has no downloadable file.")
        path = settings.DOCUMENTS_ROOT / job.output_path
        if not path.exists():
            raise Http404("File is missing from the store.")
        return FileResponse(
            open(path, "rb"),
            as_attachment=True,
            filename=f"list_{job.id}.pdf",
            content_type="application/pdf",
        )
