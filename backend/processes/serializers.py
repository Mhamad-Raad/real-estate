from rest_framework import serializers

from catalog.institutes import INSTITUTE_CODES, STEP_FOR_CODE

from .models import DuplicateOverride, Process, ProcessInstituteEntry, ProcessStep


class ProcessStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProcessStep
        fields = (
            "id",
            "step_number",
            "status",
            "start_date",
            "end_date",
            "approval_status",
            "out_of_city_flag",
            "version",
        )
        read_only_fields = ("id", "version")


class InstituteEntrySerializer(serializers.ModelSerializer):
    """A Step 2–4 institute submission (§3.4, §5.1). Fixed institutes validate their code
    against the shared enum + step; custom (Step-3 out-of-city) rows require a name instead."""

    class Meta:
        model = ProcessInstituteEntry
        fields = (
            "id",
            "process",
            "step_number",
            "institute_code",
            "is_custom",
            "custom_name",
            "assigned_lawyer",
            "approval_status",
            "approval_date",
            "version",
        )
        read_only_fields = ("id", "version")

    def validate(self, attrs):
        # Resolve each field from the payload, falling back to the existing row on partial update.
        def field(name, default=None):
            if name in attrs:
                return attrs[name]
            return getattr(self.instance, name, default) if self.instance else default

        step = field("step_number")
        is_custom = field("is_custom", False)
        code = field("institute_code", "") or ""
        if is_custom:
            if step != 3:
                raise serializers.ValidationError({"is_custom": "Custom rows exist only in Step 3."})
            if not field("custom_name"):
                raise serializers.ValidationError({"custom_name": "A custom institute needs a name."})
        else:
            if code not in INSTITUTE_CODES:
                raise serializers.ValidationError({"institute_code": "Unknown institute code."})
            if STEP_FOR_CODE.get(code) != step:
                raise serializers.ValidationError(
                    {"institute_code": "This institute does not belong to that step."}
                )
        return attrs


class ProcessListSerializer(serializers.ModelSerializer):
    client_full_name = serializers.CharField(source="client.full_name", read_only=True)
    client_pid = serializers.CharField(source="client.pid", read_only=True)
    assigned_lawyer_username = serializers.CharField(
        source="assigned_lawyer.username", read_only=True
    )

    class Meta:
        model = Process
        fields = (
            "id",
            "client",
            "client_full_name",
            "client_pid",
            "category",
            "parcel",
            "overall_status",
            "current_step",
            "duplicate_flagged",
            "assigned_lawyer",
            "assigned_lawyer_username",
            "created_at",
            "version",
        )


class ProcessDetailSerializer(ProcessListSerializer):
    steps = ProcessStepSerializer(many=True, read_only=True)
    institute_entries = InstituteEntrySerializer(many=True, read_only=True)
    step_status_summary = serializers.SerializerMethodField()
    documents = serializers.SerializerMethodField()

    class Meta(ProcessListSerializer.Meta):
        fields = ProcessListSerializer.Meta.fields + (
            "lawyer_notes",
            "steps",
            "institute_entries",
            "step_status_summary",
            "documents",
        )

    def get_step_status_summary(self, obj):
        from .status import step_status_summary

        return step_status_summary(obj)

    def get_documents(self, obj):
        from documents.serializers import DocumentSerializer

        return DocumentSerializer(obj.documents.all(), many=True).data


class ProcessCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Process
        # `duplicate_flagged` is server-computed from the identity dedup — never client input (§5.7).
        fields = ("id", "client", "parcel", "category", "assigned_lawyer")
        read_only_fields = ("id",)
        # The view resolves the assignee (self for lawyers); admins may pass one explicitly.
        extra_kwargs = {"assigned_lawyer": {"required": False}}


class ProcessUpdateSerializer(serializers.ModelSerializer):
    """Header edits a lawyer may make — never `assigned_lawyer`/`overall_status` (field-level, §7.2)."""

    class Meta:
        model = Process
        fields = ("lawyer_notes", "parcel", "category", "version")
        # Version is the optimistic-lock token the client echoes back; the service bumps it.
        read_only_fields = ("version",)


class OverrideSerializer(serializers.Serializer):
    match_reason = serializers.ChoiceField(choices=DuplicateOverride.MatchReason.choices)
    reason = serializers.CharField()
    version = serializers.IntegerField(required=False)
