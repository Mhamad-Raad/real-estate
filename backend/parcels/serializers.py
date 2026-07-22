from rest_framework import serializers

from .models import LandParcel


class LandParcelSerializer(serializers.ModelSerializer):
    class Meta:
        model = LandParcel
        fields = (
            "id",
            "parcel_number",
            "location",
            "area",
            "zone_basin",
            "registry_reference",
            "version",
            "created_at",
        )
        read_only_fields = ("id", "version", "created_at")
