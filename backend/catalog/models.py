"""Category — the A/B/C/G institute grouping, admin-managed (§3.3)."""

from django.db import models

from common.models import SoftDeleteModel


class Category(SoftDeleteModel):
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=120)

    class Meta:
        db_table = "category"
        verbose_name_plural = "categories"
        constraints = [
            # One active category per code (soft-deleted codes may be reused).
            models.UniqueConstraint(
                fields=["code"],
                condition=models.Q(is_deleted=False),
                name="ix_category_code_active",
            )
        ]

    def __str__(self):
        return f"{self.code} — {self.name}"
