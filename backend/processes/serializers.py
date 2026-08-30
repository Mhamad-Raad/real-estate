from rest_framework import serializers

from accounts.serializers import AssignableLawyerField
from catalog.institutes import INSTITUTE_CODES, STEP_FOR_CODE
from catalog.models import Category
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
            "out_of_city_flag",
            "missing",
            "version",
        )
        read_only_fields = ("id", "version")

    def get_missing(self, obj) -> list[str]:
        return missing_requirements(obj.process, obj.step_number, obj)


class InstituteEntrySerializer(serializers.ModelSerializer):
    """A Step 2–4 institute submission (§3.4, §5.1). Fixed institutes validate their code
    against the shared enum + step; custom (Step-3 out-of-city) rows carry a typed name, which
    the step's completion rule requires rather than this serializer (UC-111)."""

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
            # **The name is required, but not here.** Refusing a blank one at write time is what
            # forced the row to be created under a placeholder name, which the office then had to
            # notice and overwrite — and it fired mid-edit too, since select-all-and-retype passes
            # through empty (UC-111). `missing_requirements` holds the rule instead: a step 3 with
            # an unnamed out-of-city row is incomplete and the case cannot close over it.
        else:
            if code not in INSTITUTE_CODES:
                raise serializers.ValidationError({"institute_code": "Unknown institute code."})
            if STEP_FOR_CODE.get(code) != step:
                raise serializers.ValidationError(
                    {"institute_code": "This institute does not belong to that step."}
                )
        return attrs


class FastEntrySerializer(serializers.Serializer):
    """One finished paper allocation, as the fast-entry form sends it (UC-114).

    Flat rather than nested because the PDF rides along in the same multipart request, and a
    nested object inside multipart is a parsing problem nobody needs. The beneficiary's fields are
    still validated by `ClientSerializer` — the office's PID and birth-date rules (§4.1) apply to
    a case typed in from paper exactly as they do to one opened at the counter, and running them
    through the real serializer means the two can never drift.
    """

    full_name = serializers.CharField(max_length=200)
    pid = serializers.CharField(max_length=50)
    mother_full_name = serializers.CharField(max_length=200)
    date_of_birth = serializers.DateField()
    # Required here, unlike a normal case: the category is what gives the code its letter, it is
    # fixed for the life of the case (UC-059), and a backlog entry that arrived without one could
    # never acquire either (§3.8).
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all())
    land_id = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    # The office types these in a run and knows which are finished; a case whose paperwork stops
    # part-way stays open (the office's call, 2026-08-30).
    mark_complete = serializers.BooleanField(default=False)
    file = serializers.FileField()

    CLIENT_FIELDS = ("full_name", "pid", "mother_full_name", "date_of_birth")

    def validate(self, attrs):
        # Errors come back under the same field names the form uses, so the box that caused one
        # can be marked red without translating a nested path.
        client = ClientSerializer(
            data={
                **{name: attrs[name] for name in self.CLIENT_FIELDS},
                "date_of_birth": attrs["date_of_birth"].isoformat(),
                "category": attrs["category"].id,
            }
        )
        client.is_valid(raise_exception=True)
        attrs["client_data"] = client.validated_data
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
            # Read-only: the screens badge a backlog case so its empty steps read as history
            # rather than as work nobody finished (UC-114).
            "fast_entry",
            "assigned_lawyer",
            "assigned_lawyer_username",
            "created_at",
            # Read-only, and only ever populated on the restore desk's own listing (UC-063) —
            # a live case has none. It is what tells two deleted rows apart there.
            "deleted_at",
            "version",
        )
        # These two are output only. `fast_entry` is set by the service that files the bundle, so
        # a caller must not be able to relabel an ordinary case as backlog (UC-114).
        read_only_fields = ("fast_entry", "unique_code")


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


class ReassignSerializer(serializers.Serializer):
    """Admin-only hand-over of a case (2026-08-06). The same `AssignableLawyerField` every other
    write path uses, so a case can never be handed to someone who has left (§7.2 layer 6)."""

    assigned_lawyer = AssignableLawyerField()
    version = serializers.IntegerField(required=False)


class GenerateDocumentSerializer(serializers.Serializer):
    """Bulk list-letter request from the Processes page (§6.8) — ids are re-validated server-side."""

    process_ids = serializers.ListField(
        child=serializers.IntegerField(), allow_empty=False, max_length=500
    )
    template = serializers.IntegerField(required=False)
