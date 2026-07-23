"""Client — the land beneficiary; carries all gov-ID fields and the dedup keys (§3.3, §3.7)."""

from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.db import models

from common.models import SoftDeleteModel


class Client(SoftDeleteModel):
    class MaritalStatus(models.TextChoices):
        SINGLE = "single", "Single"
        MARRIED = "married", "Married"
        DIVORCED = "divorced", "Divorced"
        WIDOWED = "widowed", "Widowed"

    full_name = models.CharField(max_length=200)
    pid = models.CharField(max_length=50)  # national ID — unique per living person
    mother_full_name = models.CharField(max_length=200)  # duplicate-detection key only (§3.7)
    marital_status = models.CharField(
        max_length=10, choices=MaritalStatus.choices, default=MaritalStatus.SINGLE
    )
    spouse_name = models.CharField(max_length=200, blank=True)

    date_of_birth = models.DateField(null=True, blank=True)
    place_of_birth = models.CharField(max_length=120, blank=True)
    address = models.CharField(max_length=300, blank=True)
    phone = models.CharField(max_length=30, blank=True)

    category = models.ForeignKey(
        "catalog.Category",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="clients",
    )
    # The lawyer who entered this client — grants them edit rights before any process links them (§4.2).
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )

    class Meta:
        db_table = "client"
        constraints = [
            # "No duplicate client identities" — one active client row per PID (§3.7).
            models.UniqueConstraint(
                fields=["pid"],
                condition=models.Q(is_deleted=False),
                name="ix_client_pid_active",
            )
        ]
        indexes = [
            # Trigram GIN for fast fuzzy name search and mother-name dedup matching (§3.7).
            GinIndex(name="ix_client_name_trgm", fields=["full_name"], opclasses=["gin_trgm_ops"]),
            GinIndex(
                name="ix_client_mother_trgm",
                fields=["mother_full_name"],
                opclasses=["gin_trgm_ops"],
            ),
        ]

    @property
    def is_married(self) -> bool:
        return self.marital_status == self.MaritalStatus.MARRIED

    def __str__(self):
        return f"{self.full_name} ({self.pid})"
