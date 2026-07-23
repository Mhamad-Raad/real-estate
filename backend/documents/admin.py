from django.contrib import admin

from .models import Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("display_filename", "process", "step_number", "input_source", "created_at")
    list_filter = ("input_source", "step_number", "verification_status")
    search_fields = ("display_filename", "document_type")
