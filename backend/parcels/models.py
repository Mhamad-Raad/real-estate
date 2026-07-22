"""LandParcel — the land being allocated (§3.3)."""

from django.db import models

from common.models import SoftDeleteModel


class LandParcel(SoftDeleteModel):
    parcel_number = models.CharField(max_length=60)
    location = models.CharField(max_length=200, blank=True)
    area = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    zone_basin = models.CharField(max_length=120, blank=True)
    registry_reference = models.CharField(max_length=120, blank=True)

    class Meta:
        db_table = "land_parcel"
        indexes = [models.Index(fields=["parcel_number"], name="ix_parcel_number")]

    def __str__(self):
        return self.parcel_number
