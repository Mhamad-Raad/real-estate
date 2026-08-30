"""Base models and the append-only audit log shared by every domain app (§3.1, §11)."""

from django.conf import settings
from django.db import models


class ActiveManager(models.Manager):
    """Default manager: hides soft-deleted rows so lists/search/reports never leak them."""

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class JobStatus(models.TextChoices):
    """Shared lifecycle for every background job (OCR reads, PDF generation).

    Status lives in the database rather than Celery's result backend: it survives a broker
    restart, it is what the UI polls, and a failure keeps its reason instead of vanishing.
    """

    PENDING = "pending", "Pending"
    RUNNING = "running", "Running"
    DONE = "done", "Done"
    FAILED = "failed", "Failed"


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SoftDeleteModel(TimeStampedModel):
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    # Optimistic-lock counter — the service layer bumps it on each write; a stale PATCH → HTTP 409.
    version = models.PositiveIntegerField(default=1)

    objects = ActiveManager()  # hides is_deleted=True
    all_objects = models.Manager()  # includes soft-deleted (restore/admin/audit)

    class Meta:
        abstract = True


class ActivityLog(TimeStampedModel):
    """Immutable audit trail — one row per create/update/delete/restore/verify/override/
    generate/login. Written only from the service layer (never signals), never updated/deleted."""

    class Action(models.TextChoices):
        CREATE = "create", "Create"
        UPDATE = "update", "Update"
        DELETE = "delete", "Delete"
        RESTORE = "restore", "Restore"
        VERIFY = "verify", "Verify"
        OVERRIDE = "override", "Override"
        GENERATE = "generate", "Generate"
        LOGIN = "login", "Login"
        LOGOUT = "logout", "Logout"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="activity_logs",
    )
    action = models.CharField(max_length=20, choices=Action.choices)
    entity_type = models.CharField(max_length=100)
    entity_id = models.CharField(max_length=64, blank=True)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    # The build that wrote this row, so a bad record can be traced to the version that produced
    # it. Null on every row written before build stamping existed — absence means "before", not
    # "unknown", and the column stays nullable so the append-only trail is never back-filled.
    app_build = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        db_table = "activity_log"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["entity_type", "entity_id"]),
            models.Index(fields=["actor", "-created_at"]),
            models.Index(fields=["action", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.action} {self.entity_type}#{self.entity_id} by {self.actor_id}"
