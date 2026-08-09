from rest_framework import serializers

from .models import ActivityLog


class DateRangeFilterSerializer(serializers.Serializer):
    """Base for read-endpoint query validation (§12 input safety).

    Query strings are raw user input: without this, an unparseable date or a non-integer id
    reaches `filter()` and raises out of the view as a 500 rather than a 400. Subclasses declare
    their own field names because the API is not consistent about them (`date_from` on reports,
    `created_after` on activities and processes).
    """

    start_field: str = ""
    end_field: str = ""

    def validate(self, attrs):
        start, end = attrs.get(self.start_field), attrs.get(self.end_field)
        if start and end and start > end:
            raise serializers.ValidationError(
                f"{self.start_field} must not be after {self.end_field}."
            )
        return attrs


class ActivityFilterSerializer(DateRangeFilterSerializer):
    """Validates the Activities query string (§11.3)."""

    start_field = "created_after"
    end_field = "created_before"

    actor = serializers.IntegerField(required=False)
    action = serializers.ChoiceField(choices=ActivityLog.Action.choices, required=False)
    entity_type = serializers.CharField(required=False, max_length=100)
    entity_id = serializers.CharField(required=False, max_length=64)
    created_after = serializers.DateField(required=False)
    created_before = serializers.DateField(required=False)


class ActivityLogSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(source="actor.username", default="", read_only=True)

    class Meta:
        model = ActivityLog
        fields = (
            "id",
            "actor",
            "actor_username",
            "action",
            "entity_type",
            "entity_id",
            "before",
            "after",
            "ip_address",
            "app_build",
            "created_at",
        )
        # The whole model is read-only: the trail is append-only and written only by the
        # service layer (§11.2). Nothing may reach it through the API.
        read_only_fields = fields
