from django.contrib import admin

from .models import Client


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("full_name", "pid", "marital_status", "is_deleted")
    search_fields = ("full_name", "pid", "mother_full_name")
    list_filter = ("marital_status", "is_deleted")
