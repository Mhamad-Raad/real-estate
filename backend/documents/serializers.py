from rest_framework import serializers

from catalog.document_types import DOCUMENT_TYPE_CODES
from processes.models import Process, ProcessInstituteEntry

from .models import Document, DocumentTemplate, GenerationJob


class DocumentSerializer(serializers.ModelSerializer):
    """Read shape — metadata only; bytes are served by the download action (§4.4)."""

    class Meta:
        model = Document
        fields = (
            "id",
            "process",
            "step_number",
            "document_type",
            "institute_entry",
            "input_source",
            "ocr_status",
            "verification_status",
            "display_filename",
            "size_bytes",
            # How many sides of a card are on file: both are stored as one document (UC-083).
            "page_count",
            "uploaded_by",
            "created_at",
            "version",
        )
        read_only_fields = fields


class DocumentUploadSerializer(serializers.Serializer):
    """Multipart upload input (§4.4). The view reads `file` bytes and calls the service."""

    process = serializers.PrimaryKeyRelatedField(queryset=Process.objects.all())
    step_number = serializers.IntegerField(min_value=1, max_value=5)
    document_type = serializers.CharField(max_length=60)
    input_source = serializers.ChoiceField(
        choices=[Document.InputSource.IMPORTED, Document.InputSource.SCANNED],
        default=Document.InputSource.IMPORTED,
    )
    institute_entry = serializers.PrimaryKeyRelatedField(
        queryset=ProcessInstituteEntry.objects.all(), required=False, allow_null=True
    )
    file = serializers.FileField()

    def validate_document_type(self, value):
        """Only the shared vocabulary (§6.7) — an unknown type would file a document under a
        label no step requires and no upload slot renders, leaving it invisible in the UI."""
        if value not in DOCUMENT_TYPE_CODES:
            raise serializers.ValidationError(f"Unknown document type '{value}'.")
        return value

    def validate(self, attrs):
        # An institute entry must belong to the same process and step it's being attached under.
        entry = attrs.get("institute_entry")
        if entry and (entry.process_id != attrs["process"].id or entry.step_number != attrs["step_number"]):
            raise serializers.ValidationError(
                {"institute_entry": "Entry does not belong to this process/step."}
            )
        return attrs


class DocumentTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentTemplate
        fields = (
            "id",
            "template_type",
            "name",
            "original_filename",
            "size_bytes",
            # Whether the row is a blank form the office prints or a letter the system fills in
            # (§6.6). It rides on the row itself because that is what every screen holds — reading
            # it from the separate vocabulary endpoint left a form labelled as a letter, without
            # its Print button, whenever that second request had not landed.
            "is_blank_form",
            "is_active",
            "uploaded_by",
            "version",
            "created_at",
        )
        read_only_fields = (
            "id",
            "original_filename",
            "size_bytes",
            "uploaded_by",
            "version",
            "created_at",
        )


class GenerationJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = GenerationJob
        fields = (
            "id",
            "kind",
            "status",
            "template",
            "process",
            "process_ids",
            "document",
            "error",
            "requested_by",
            "created_at",
        )
        read_only_fields = fields
