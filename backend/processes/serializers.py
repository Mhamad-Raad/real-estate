from rest_framework import serializers

from .models import DuplicateOverride, Process, ProcessStep


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

    class Meta(ProcessListSerializer.Meta):
        fields = ProcessListSerializer.Meta.fields + ("lawyer_notes", "steps")


class ProcessCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Process
        fields = ("id", "client", "parcel", "category", "assigned_lawyer", "duplicate_flagged")
        read_only_fields = ("id",)
        # The view resolves the assignee (self for lawyers); admins may pass one explicitly.
        extra_kwargs = {"assigned_lawyer": {"required": False}}


class ProcessUpdateSerializer(serializers.ModelSerializer):
    """Header edits a lawyer may make — never `assigned_lawyer`/`overall_status` (field-level, §7.2)."""

    class Meta:
        model = Process
        fields = ("lawyer_notes", "parcel", "category", "version")


class OverrideSerializer(serializers.Serializer):
    match_reason = serializers.ChoiceField(choices=DuplicateOverride.MatchReason.choices)
    reason = serializers.CharField()
