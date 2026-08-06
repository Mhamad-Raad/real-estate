"""Documents API — upload (multipart), metadata, permission-checked download, soft-delete (§4.4)."""

import io

from django.conf import settings
from django.http import FileResponse, Http404
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from common.viewsets import AuditedSoftDeleteViewSet
from processes.services import recompute_step

from .models import Document, DocumentTemplate, GenerationJob
from .filestore import bulk_job_filename
from .permissions import IsDocumentEditorOrAdmin
from .selectors import documents_for_process
from .preview import render_template_preview
from .rendering import RenderError
from .serializers import (
    DocumentSerializer,
    DocumentTemplateSerializer,
    DocumentUploadSerializer,
    GenerationJobSerializer,
)
from .services import create_document, read_upload


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
            content=read_upload(upload),
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


class DocumentTemplateViewSet(ReadOnlyModelViewSet):
    """Letter templates, **read-only** (§6.6, UC-010).

    Templates are installed by a developer with `manage.py install_templates`, not uploaded from
    the running app: the active letter is a reviewed, version-controlled artifact, and nobody can
    break generation by uploading a wrong or corrupt file. Read-only here means read-only at the
    boundary — `POST`/`PATCH`/`DELETE` are 405 — because hiding the buttons is never the boundary
    (§7.2). Same treatment the audit trail already gets.
    """

    serializer_class = DocumentTemplateSerializer
    # Unpaginated on purpose: the screen groups by letter type, and a grouping cannot be paged
    # coherently — an active template on page 2 would render its group as "none installed" on
    # page 1. The set is bounded by the number of letters the office uses, times their revisions.
    pagination_class = None

    def get_queryset(self):
        # Active first within each type, then newest: the row that matters leads its group, and
        # `install_templates` never deletes a retired version (§6.6), so the tail only grows.
        qs = DocumentTemplate.objects.select_related("uploaded_by").order_by(
            "template_type", "-is_active", "-created_at"
        )
        template_type = self.request.query_params.get("template_type")
        return qs.filter(template_type=template_type) if template_type else qs

    @action(detail=True, methods=["get"])
    def preview(self, request, pk=None):
        """Render this `.docx` to PDF so the screen can show the letter, not just a filename.

        Filled with clearly-marked **sample** data: a blank template renders empty gaps and an
        empty beneficiary table, which reads as broken rather than as "this is the letter".
        Rendered on demand — LibreOffice takes a second or two and this is an occasional click.
        """
        template = self.get_object()
        try:
            pdf = render_template_preview(template)
        except RenderError as exc:
            raise Http404(str(exc))
        return FileResponse(
            io.BytesIO(pdf),
            as_attachment=False,
            filename=f"{template.template_type}_preview.pdf",
            content_type="application/pdf",
        )


class GenerationJobViewSet(ReadOnlyModelViewSet):
    """Poll a generation job and download a finished list letter (§6.6, §6.8)."""

    serializer_class = GenerationJobSerializer

    def get_queryset(self):
        qs = GenerationJob.objects.select_related("template", "process").order_by("-created_at")
        # A job exposes what its requester asked for, so only they (or an admin) may read it.
        return qs if self.request.user.is_admin else qs.filter(requested_by=self.request.user)

    @action(detail=True, methods=["get"])
    def file(self, request, pk=None):
        """Stream a finished list letter. Single-beneficiary letters are served as Documents.

        The name is composed here, not by the caller: every other file in this system is named by
        the server (§6.7), and this endpoint used to hand back `list_<id>.pdf` **whatever the job
        was** — so a code list arrived called a case list (UC-066).
        """
        job = self.get_object()
        if job.status != GenerationJob.Status.DONE or not job.output_path:
            raise Http404("This job has no downloadable file.")
        path = settings.DOCUMENTS_ROOT / job.output_path
        if not path.exists():
            raise Http404("File is missing from the store.")
        return FileResponse(
            open(path, "rb"),
            as_attachment=True,
            filename=bulk_job_filename(job),
            content_type="application/pdf",
        )
