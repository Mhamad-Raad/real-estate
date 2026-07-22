from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Land-Allocation", {"fields": ("role",)}),
    )
    list_display = ("username", "role", "is_staff", "is_active")
