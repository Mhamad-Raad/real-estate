from rest_framework import serializers

from .models import ActivityLog


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
            "created_at",
        )
        # The whole model is read-only: the trail is append-only and written only by the
        # service layer (§11.2). Nothing may reach it through the API.
        read_only_fields = fields
