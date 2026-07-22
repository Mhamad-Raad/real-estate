from django.contrib import admin

from .models import DuplicateOverride, Process, ProcessStep


class ProcessStepInline(admin.TabularInline):
    model = ProcessStep
    extra = 0


@admin.register(Process)
class ProcessAdmin(admin.ModelAdmin):
    list_display = ("id", "client", "overall_status", "current_step", "assigned_lawyer", "duplicate_flagged")
    list_filter = ("overall_status", "duplicate_flagged", "is_deleted")
    inlines = [ProcessStepInline]


@admin.register(DuplicateOverride)
class DuplicateOverrideAdmin(admin.ModelAdmin):
    list_display = ("id", "process", "client", "match_reason", "overridden_by")
