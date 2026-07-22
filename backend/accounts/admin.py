from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Land-Allocation", {"fields": ("role", "language", "theme")}),
    )
    list_display = ("username", "role", "language", "is_staff", "is_active")
