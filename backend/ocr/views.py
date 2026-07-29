"""OCR endpoints — thin HTTP over `services` (§6.5, §14.2)."""

from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.mixins import RetrieveModelMixin
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from documents.models import Document

from .models import OcrRun
from .services import CLIENT_FIELDS, start_ocr, verify_ocr


class OcrRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = OcrRun
        fields = (
            "id",
            "document",
            "status",
            "draft",
            "error",
            "verified_at",
            "verified_by",
            "created_at",
        )
        read_only_fields = fields


class StartOcrSerializer(serializers.Serializer):
    document = serializers.PrimaryKeyRelatedField(queryset=Document.objects.all())


class VerifySerializer(serializers.Serializer):
    """What the human confirmed on screen — every field optional and freely editable."""

    pid = serializers.CharField(required=False, allow_blank=True, max_length=50)
    full_name = serializers.CharField(required=False, allow_blank=True, max_length=200)
    mother_full_name = serializers.CharField(required=False, allow_blank=True, max_length=200)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    # The client's version as the screen loaded it — this writes to the same columns the client
    # details panel does, so the optimistic lock is mandatory here too (§4.1).
    client_version = serializers.IntegerField()

    def validate(self, attrs):
        if not any(name in attrs for name in CLIENT_FIELDS):
            raise serializers.ValidationError("No fields were submitted.")
        return attrs


class OcrRunViewSet(RetrieveModelMixin, GenericViewSet):
    """Start a reading, poll it, then verify it.

    No list/update/delete: a run is an immutable record of one reading. Object permissions come
    from the process the document belongs to — only its assignee or an admin may act on it.
    """

    serializer_class = OcrRunSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return OcrRun.objects.select_related("document__process")

    def _assert_may_write(self, document):
        user = self.request.user
        if not (user.is_admin or document.process.assigned_lawyer_id == user.id):
            raise PermissionDenied("Only the assigned lawyer or an admin can do this.")

    def create(self, request):
        payload = StartOcrSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        document = payload.validated_data["document"]
        self._assert_may_write(document)
        run = start_ocr(document=document, actor=request.user, request=request)
        return Response(OcrRunSerializer(run).data, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None):
        run = self.get_object()
        self._assert_may_write(run.document)
        payload = VerifySerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        values = dict(payload.validated_data)
        client_version = values.pop("client_version")
        run = verify_ocr(
            run=run,
            values=values,
            client_version=client_version,
            actor=request.user,
            request=request,
        )
        return Response(OcrRunSerializer(run).data)
