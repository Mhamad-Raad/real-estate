"""Card-scan endpoints — thin HTTP over `services` (§6.5, §6.7, §14.2)."""

from django.conf import settings
from django.http import FileResponse
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.mixins import RetrieveModelMixin
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from accounts.models import User
from catalog.models import Category
from clients.models import Client

from .models import CardScan
from .services import CLIENT_FIELDS, active_process_for, confirm_scan, stage_scan


class CardScanSerializer(serializers.ModelSerializer):
    class Meta:
        model = CardScan
        fields = (
            "id",
            "document_type",
            "status",
            "draft",
            "error",
            "document",
            "confirmed_at",
            "confirmed_by",
            "created_at",
        )
        read_only_fields = fields


class StageScanSerializer(serializers.Serializer):
    """Both sides of one card. The back is optional — a lawyer may photograph only the front,
    which costs the MRZ (and so the check-digit-verified dates), and the draft says so."""

    file = serializers.FileField()
    back = serializers.FileField(required=False, allow_null=True)
    document_type = serializers.CharField(max_length=60)


class ConfirmSerializer(serializers.Serializer):
    """What the human confirmed on screen — every card field optional and freely editable.

    Optional because a failed reading is still confirmable: the lawyer types the values in and
    they arrive here exactly as a corrected reading would.
    """

    pid = serializers.CharField(required=False, allow_blank=True, max_length=50)
    full_name = serializers.CharField(required=False, allow_blank=True, max_length=200)
    mother_full_name = serializers.CharField(required=False, allow_blank=True, max_length=200)
    date_of_birth = serializers.DateField(required=False, allow_null=True)

    # Absent → the card creates the person; present → it updates someone already on file (a
    # spouse card, or a replacement scan), and then the optimistic lock applies.
    client = serializers.PrimaryKeyRelatedField(
        queryset=Client.objects.all(), required=False, allow_null=True
    )
    client_version = serializers.IntegerField(required=False)
    # Only used when creating: a new case needs an owner, and a category if one is known yet.
    assigned_lawyer = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(is_active=True), required=False, allow_null=True
    )
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), required=False, allow_null=True
    )

    def validate(self, attrs):
        if not any(name in attrs for name in CLIENT_FIELDS):
            raise serializers.ValidationError("No fields were submitted.")
        if attrs.get("client") and attrs.get("client_version") is None:
            raise serializers.ValidationError(
                {"client_version": "This field is required when updating an existing client."}
            )
        return attrs


class CardScanViewSet(RetrieveModelMixin, GenericViewSet):
    """Stage a card, poll its reading, preview it, then confirm it into real records.

    No list/update/delete: a scan is a staging record, and once confirmed it is history. A lawyer
    sees only their own scans — an unconfirmed scan carries a citizen's ID with nobody's name yet
    attached to gate it, so it stays with the person who took it.
    """

    serializer_class = CardScanSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        scans = CardScan.objects.all()
        if self.request.user.is_admin:
            return scans
        return scans.filter(uploaded_by=self.request.user)

    def create(self, request):
        payload = StageScanSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        upload = payload.validated_data["file"]
        back = payload.validated_data.get("back")
        scan = stage_scan(
            content=upload.read(),
            back=back.read() if back else None,
            document_type=payload.validated_data["document_type"],
            actor=request.user,
            original_filename=getattr(upload, "name", ""),
            request=request,
        )
        return Response(CardScanSerializer(scan).data, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["get"])
    def file(self, request, pk=None):
        """The staged PDF, for the preview pane beside the fields."""
        scan = self.get_object()
        path = settings.DOCUMENTS_ROOT / scan.file_path if scan.file_path else None
        if path is None or not path.exists():
            raise NotFound("This scan has no staged file; it has already been filed.")
        return FileResponse(path.open("rb"), content_type="application/pdf")

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        scan = self.get_object()
        payload = ConfirmSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = dict(payload.validated_data)
        client = data.pop("client", None)
        if client is not None:
            self._assert_may_write(client)
        scan = confirm_scan(
            scan=scan,
            client=client,
            client_version=data.pop("client_version", None),
            assigned_lawyer=data.pop("assigned_lawyer", None),
            category=data.pop("category", None),
            values=data,
            actor=request.user,
            request=request,
        )
        return Response(CardScanSerializer(scan).data)

    def _assert_may_write(self, client):
        """Filing onto an existing case follows that case's assignment, like any other upload.

        Checked against the *same* case the write will target, not "any case of this client":
        someone assigned only to a rejected case would otherwise be let through to the live one.
        """
        user = self.request.user
        if user.is_admin:
            return
        if active_process_for(client).assigned_lawyer_id != user.id:
            raise PermissionDenied("Only the assigned lawyer or an admin can do this.")
