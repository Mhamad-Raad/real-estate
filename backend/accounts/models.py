"""Custom User: login account, RBAC role, and per-user UI preferences (§7)."""

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        LAWYER = "lawyer", "Lawyer"

    class Language(models.TextChoices):
        SORANI = "ckb", "Kurdish (Sorani)"
        ARABIC = "ar", "Arabic"
        ENGLISH = "en", "English"

    class Theme(models.TextChoices):
        LIGHT = "light", "Light"
        DARK = "dark", "Dark"

    role = models.CharField(max_length=10, choices=Role.choices, default=Role.LAWYER)
    language = models.CharField(
        max_length=3, choices=Language.choices, default=Language.SORANI
    )
    theme = models.CharField(max_length=5, choices=Theme.choices, default=Theme.LIGHT)

    @property
    def is_admin(self) -> bool:
        return self.role == self.Role.ADMIN

    def __str__(self):
        return self.username
