from rest_framework import serializers

from common.validators import normalise_pid, validate_birth_date, validate_phone, validate_pid

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

    # Per-field, so DRF reports each against the input that caused it and the screen can mark that
    # one red. A `validate()` check would name the whole object instead (the trap batch 26 hit).
    # The national ID is 12 digits (office rule, 2026-08-20), but **only where one is being set or
    # changed**. Their existing records carry several lengths, and this form submits the whole
    # object — so validating unconditionally would refuse a phone correction on a beneficiary whose
    # PID nobody touched. See `common.validators.validate_pid`.
    def _validated_pid(self, value, field: str):
        # **Normalised on both branches.** Returning the raw input when the value is "unchanged"
        # looked harmless and was not: re-sending an existing ASCII PID written in Arabic-Indic
        # compares equal *after folding*, so it took the skip — and then stored the unfolded form,
        # leaving one person's ID in two shapes and invisible to the dedup index (§5.7).
        canonical = normalise_pid(value)
        if self.instance is not None and canonical == getattr(self.instance, field):
            return canonical  # unchanged; carried along by an edit to some other field
        return validate_pid(value)

    def validate_pid(self, value):
        return self._validated_pid(value, "pid")

    def validate_spouse_pid(self, value):
        # Optional by design — "leave blank if unknown" (§5.7). A blank spouse PID simply means the
        # household check has nothing to match on; only a value that is actually there is held to
        # the format.
        return value if not (value or "").strip() else self._validated_pid(value, "spouse_pid")

    def validate_phone(self, value):
        return validate_phone(value)

    def validate_date_of_birth(self, value):
        return validate_birth_date(value)

    def validate_spouse_date_of_birth(self, value):
        return validate_birth_date(value)

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

    # **Folded, exactly as a stored PID is.** This check is the warning the office sees *before*
    # saving, and it searches by equality — so a lawyer typing `١٩٩٠…` against a row stored as
    # `1990…` was told "no duplicate" about a person who is already on file. It must not be
    # validated here, only normalised: the check runs against half-typed input, and refusing a
    # 6-digit entry would turn the duplicate warning into a form error.
    def validate_pid(self, value):
        return normalise_pid(value)

    def validate_spouse_pid(self, value):
        return normalise_pid(value)
