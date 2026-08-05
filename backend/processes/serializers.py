from rest_framework import serializers

from accounts.serializers import AssignableLawyerField
from catalog.institutes import INSTITUTE_CODES, STEP_FOR_CODE
from clients.serializers import ClientSerializer

from .models import DuplicateOverride, Process, ProcessInstituteEntry, ProcessStep
from .status import missing_requirements


class ProcessStepSerializer(serializers.ModelSerializer):
    # What this step still needs — drives the "proceed anyway?" warning (§5.2).
    missing = serializers.SerializerMethodField()

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
            "missing",
            "version",
        )
        read_only_fields = ("id", "version")

    def get_missing(self, obj) -> list[str]:
        return missing_requirements(obj.process, obj.step_number, obj)


class InstituteEntrySerializer(serializers.ModelSerializer):
    """A Step 2–4 institute submission (§3.4, §5.1). Fixed institutes validate their code
    against the shared enum + step; custom (Step-3 out-of-city) rows require a name instead."""

    assigned_lawyer = AssignableLawyerField(required=False, allow_null=True)

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
            "unique_code",
            "land_id",
            "land_address",
            "overall_status",
            "current_step",
            "duplicate_flagged",
            "similar_name_flagged",
            "assigned_lawyer",
            "assigned_lawyer_username",
            "created_at",
            # Read-only, and only ever populated on the restore desk's own listing (UC-063) —
            # a live case has none. It is what tells two deleted rows apart there.
            "deleted_at",
            "version",
        )


class ProcessDetailSerializer(ProcessListSerializer):
    steps = ProcessStepSerializer(many=True, read_only=True)
    institute_entries = InstituteEntrySerializer(many=True, read_only=True)
    step_status_summary = serializers.SerializerMethodField()
    documents = serializers.SerializerMethodField()
    # Step 1 edits the beneficiary's own details (birth date, spouse) inline, and the spouse-ID
    # upload slot only appears for a married client — both need the client row, not just a name.
    client_detail = serializers.SerializerMethodField()

    class Meta(ProcessListSerializer.Meta):
        fields = ProcessListSerializer.Meta.fields + (
            "lawyer_notes",
            "steps",
            "institute_entries",
            "step_status_summary",
            "documents",
            "client_detail",
        )

    def get_client_detail(self, obj):
        return ClientSerializer(obj.client).data

    def get_step_status_summary(self, obj):
        from .status import step_status_summary

        return step_status_summary(obj)

    def get_documents(self, obj):
        from documents.serializers import DocumentSerializer

        return DocumentSerializer(obj.documents.all(), many=True).data


class ProcessCreateSerializer(serializers.ModelSerializer):
    """The Step-1 intake payload: the beneficiary (existing or brand new) plus the land (§5, UC-024)."""

    # Creating the person here is the whole point of the intake form — reuse `ClientSerializer` so
    # the married-spouse rules and field validation cannot drift from the Clients API (§14.2).
    client_data = ClientSerializer(required=False, write_only=True)
    assigned_lawyer = AssignableLawyerField(required=False, allow_null=True)

    class Meta:
        model = Process
        # `duplicate_flagged` is server-computed from the identity dedup — never client input (§5.7).
        fields = ("id", "client", "client_data", "category", "assigned_lawyer", "land_id", "land_address")
        read_only_fields = ("id",)
        extra_kwargs = {
            # Not `required` — see validate(): re-applying passes only the client and inherits
            # their category, so demanding it here would reject a legitimate path (UC-028).
            # The view resolves the assignee (self for lawyers); admins may pass one explicitly.
            "assigned_lawyer": {"required": False},
            # Exactly one of `client` / `client_data` — enforced in validate(), not by `required`.
            "client": {"required": False},
            "land_id": {"required": False},
            "land_address": {"required": False},
        }

    def validate(self, attrs):
        if bool(attrs.get("client")) == bool(attrs.get("client_data")):
            raise serializers.ValidationError(
                {"client": "Provide exactly one of `client` (existing) or `client_data` (new)."}
            )
        # Every case must be numberable (UC-056): the unique code takes its first letter from the
        # category, and the category can never be set afterwards (UC-059). So the rule is that a
        # category must be **resolvable**, not that it must always be typed — re-applying after a
        # rejection passes only the client and inherits theirs (UC-028).
        client = attrs.get("client")
        if attrs.get("category") is None and (client is None or client.category_id is None):
            raise serializers.ValidationError(
                {"category": "A case must be opened in a category; it cannot be set later."}
            )
        return attrs


class ProcessUpdateSerializer(serializers.ModelSerializer):
    """Header edits a lawyer may make — never `assigned_lawyer`/`overall_status` (field-level, §7.2)."""

    class Meta:
        model = Process
        # Step-1 header edits: land details + notes. **Not the category** — see validate() below,
        # and **not the case number**, which the system owns end to end (§3.8, UC-064).
        fields = ("lawyer_notes", "land_id", "land_address", "version")
        # Version is the optimistic-lock token the client echoes back; the service bumps it.
        read_only_fields = ("version",)

    def validate(self, attrs):
        """Refuse a category change outright rather than dropping it silently (UC-059).

        The office's rule: a case's category is fixed at creation; moving one means deleting it and
        opening a new case in the other category. Leaving `category` off `fields` would be enough to
        ignore it, but a caller that sent it would get a 200 and believe it had worked. It matters
        more once the unique code exists (UC-056), whose first letter *is* the category — a code
        already printed on letters that have gone out must never come to contradict the case.
        """
        if "category" in self.initial_data:
            incoming = self.initial_data["category"]
            current = self.instance.category_id if self.instance else None
            unchanged = incoming in (current, str(current) if current is not None else None)
            if not unchanged:
                raise serializers.ValidationError(
                    {"category": "A case's category cannot be changed after it is created."}
                )
        return attrs


class OverrideSerializer(serializers.Serializer):
    match_reason = serializers.ChoiceField(choices=DuplicateOverride.MatchReason.choices)
    reason = serializers.CharField()
    version = serializers.IntegerField(required=False)


class GenerateDocumentSerializer(serializers.Serializer):
    """Bulk list-letter request from the Processes page (§6.8) — ids are re-validated server-side."""

    process_ids = serializers.ListField(
        child=serializers.IntegerField(), allow_empty=False, max_length=500
    )
    template = serializers.IntegerField(required=False)
