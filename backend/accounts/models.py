"""Custom User: login account, RBAC role (§7). Soft-deletable like every domain model."""

from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        LAWYER = "lawyer", "Lawyer"

    # UI preferences (theme/language) are client-only concerns kept in the browser, not here.
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.LAWYER)

    # Soft-delete parity with SoftDeleteModel — User can't multi-inherit it (AbstractUser clash),
    # so the same fields are mirrored here; a soft-deleted user is also deactivated (can't log in).
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    version = models.PositiveIntegerField(default=1)  # optimistic-lock counter (§4.1, §12)

    objects = UserManager()  # sees all rows; auth relies on is_active to bar deleted users
    all_objects = UserManager()  # explicit alias so shared CRUD/restore code can find every row

    @property
    def is_admin(self) -> bool:
        return self.role == self.Role.ADMIN

    def __str__(self):
        return self.username
