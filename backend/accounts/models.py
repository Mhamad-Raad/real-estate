"""Custom User: login account, RBAC role, and per-user UI preferences (§7)."""

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        LAWYER = "lawyer", "Lawyer"

    # UI preferences (theme/language) are client-only concerns kept in the browser, not here.
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.LAWYER)

    @property
    def is_admin(self) -> bool:
        return self.role == self.Role.ADMIN

    def __str__(self):
        return self.username
