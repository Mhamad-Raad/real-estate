from django.contrib import admin

from .models import LandParcel


@admin.register(LandParcel)
class LandParcelAdmin(admin.ModelAdmin):
    list_display = ("parcel_number", "location", "is_deleted")
    search_fields = ("parcel_number", "location")
