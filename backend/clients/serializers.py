from rest_framework import serializers

from .models import Client


class ClientSerializer(serializers.ModelSerializer):
    is_married = serializers.BooleanField(read_only=True)

    class Meta:
        model = Client
        fields = (
            "id",
            "full_name",
            "pid",
            "mother_full_name",
            "marital_status",
            "spouse_name",
            "spouse_date_of_birth",
            "spouse_mother_full_name",
            "spouse_pid",
            "is_married",
            "date_of_birth",
            "place_of_birth",
            "address",
            "phone",
            "category",
            "created_by",
            "version",
            "created_at",
            # Only ever set on the restore desk's own listing (UC-063); a live client has none.
            "deleted_at",
        )
        read_only_fields = ("id", "created_by", "version", "created_at", "deleted_at")

    # The letter prints a spouse row of name / birth date / mother's name, so a married client
    # needs all three — the same set the DB check constraint enforces (§6.6).
    SPOUSE_FIELDS = ("spouse_name", "spouse_date_of_birth", "spouse_mother_full_name")

    def validate(self, attrs):
        def resolved(field):
            return attrs.get(field, getattr(self.instance, field, None))

        if resolved("marital_status") == Client.MaritalStatus.MARRIED:
            missing = {
                field: "Required when marital status is married."
                for field in self.SPOUSE_FIELDS
                if not (str(resolved(field) or "").strip())
            }
            if missing:
                raise serializers.ValidationError(missing)
        else:
            # Clear spouse details a divorce or bereavement left behind, so the letter prints the
            # blank spouse row the paper form expects rather than a former spouse's data.
            # `spouse_pid` especially: left behind, it would keep a former spouse flagged as an
            # already-allocated household and block an application they are entitled to make.
            attrs.update({"spouse_name": "", "spouse_mother_full_name": "", "spouse_pid": ""})
            attrs["spouse_date_of_birth"] = None
        return attrs


class DuplicateCheckSerializer(serializers.Serializer):
    """Input for POST /clients/duplicate-check/ (§5.7)."""

    pid = serializers.CharField(required=False, allow_blank=True, default="")
    mother_full_name = serializers.CharField(required=False, allow_blank=True, default="")
    # A household may hold one allocation, so the spouse's ID is part of the check (§5.7).
    spouse_pid = serializers.CharField(required=False, allow_blank=True, default="")
    exclude_id = serializers.IntegerField(required=False)
