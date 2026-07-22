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
            "is_married",
            "date_of_birth",
            "place_of_birth",
            "address",
            "phone",
            "category",
            "version",
            "created_at",
        )
        read_only_fields = ("id", "version", "created_at")

    def validate(self, attrs):
        # A married client must name a spouse (drives the spouse eligibility PDF in Step 1, §3.5).
        marital = attrs.get("marital_status", getattr(self.instance, "marital_status", None))
        spouse = attrs.get("spouse_name", getattr(self.instance, "spouse_name", ""))
        if marital == Client.MaritalStatus.MARRIED and not (spouse and spouse.strip()):
            raise serializers.ValidationError(
                {"spouse_name": "Spouse name is required when marital status is married."}
            )
        return attrs


class DuplicateCheckSerializer(serializers.Serializer):
    """Input for POST /clients/duplicate-check/ (§5.7)."""

    pid = serializers.CharField(required=False, allow_blank=True, default="")
    mother_full_name = serializers.CharField(required=False, allow_blank=True, default="")
    exclude_id = serializers.IntegerField(required=False)
