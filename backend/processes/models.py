"""Process — the central allocation case — plus its per-step rows and duplicate-override log.

The `ix_process_active_alloc` partial-unique index is the storage-level "no land twice"
guarantee (§3.7, §5.7): at most one non-rejected, non-deleted allocation per client.
"""

from django.conf import settings
from django.db import models

from common.models import SoftDeleteModel


class Process(SoftDeleteModel):
    class OverallStatus(models.TextChoices):
        DRAFT = "draft", "Draft"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETE = "complete", "Complete"
        REJECTED = "rejected", "Rejected"

    client = models.ForeignKey(
        "clients.Client", on_delete=models.PROTECT, related_name="processes"
    )
    parcel = models.ForeignKey(
        "parcels.LandParcel",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="processes",
    )
    category = models.ForeignKey(
        "catalog.Category",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="processes",
    )
    # Process-wide assignee — the ONLY assignment that grants edit/delete rights (§7.2).
    assigned_lawyer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="assigned_processes"
    )

    overall_status = models.CharField(
        max_length=12, choices=OverallStatus.choices, default=OverallStatus.DRAFT
    )
    current_step = models.PositiveSmallIntegerField(default=1)
    lawyer_notes = models.TextField(blank=True)
    # Set when a duplicate warning fired; blocks advancing past Step 1 until an admin overrides.
    duplicate_flagged = models.BooleanField(default=False)

    class Meta:
        db_table = "process"
        constraints = [
            # THE "no land twice" guarantee — one active (non-rejected) allocation per client.
            models.UniqueConstraint(
                fields=["client"],
                condition=models.Q(is_deleted=False) & ~models.Q(overall_status="rejected"),
                name="ix_process_active_alloc",
            )
        ]
        indexes = [
            models.Index(fields=["created_at"], name="ix_process_created_at"),
            models.Index(fields=["client"], name="ix_process_client"),
            models.Index(
                fields=["category", "overall_status", "assigned_lawyer"],
                name="ix_process_filters",
            ),
        ]

    def __str__(self):
        return f"Process #{self.pk} — {self.client_id}"


class ProcessStep(SoftDeleteModel):
    class Status(models.TextChoices):
        NOT_STARTED = "not_started", "Not started"
        IN_PROGRESS = "in_progress", "In progress"
        MISSING = "missing", "Missing files"
        COMPLETE = "complete", "Complete"

    class ApprovalStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    process = models.ForeignKey(Process, on_delete=models.PROTECT, related_name="steps")
    step_number = models.PositiveSmallIntegerField()
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.NOT_STARTED
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    approval_status = models.CharField(
        max_length=10, choices=ApprovalStatus.choices, blank=True
    )
    out_of_city_flag = models.BooleanField(default=False)  # Step 3 out-of-city rows

    class Meta:
        db_table = "process_step"
        constraints = [
            # One active row per (process, step) — soft-deleted rows don't block re-creation.
            models.UniqueConstraint(
                fields=["process", "step_number"],
                condition=models.Q(is_deleted=False),
                name="ix_step_process_number_active",
            )
        ]

    def __str__(self):
        return f"Process #{self.process_id} step {self.step_number}"


class ProcessInstituteEntry(SoftDeleteModel):
    """One institute submission within Steps 2–4 (§3.4, §5.1). Fixed institutes carry an
    `institute_code` from the shared enum; Step-3 out-of-city rows set `is_custom` + `custom_name`."""

    class ApprovalStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    process = models.ForeignKey(
        Process, on_delete=models.PROTECT, related_name="institute_entries"
    )
    step_number = models.PositiveSmallIntegerField()  # 2, 3 or 4
    institute_code = models.CharField(max_length=40, blank=True)  # enum code; blank for custom rows
    is_custom = models.BooleanField(default=False)  # Step-3 out-of-city row
    custom_name = models.CharField(max_length=200, blank=True)
    # Per-institute assignee — distinct from the process-wide lawyer and granting no edit rights (§7.2).
    assigned_lawyer = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    approval_status = models.CharField(
        max_length=10, choices=ApprovalStatus.choices, default=ApprovalStatus.PENDING
    )
    approval_date = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "process_institute_entry"
        indexes = [
            models.Index(fields=["process", "step_number"], name="ix_entry_process"),
        ]

    def __str__(self):
        return f"p#{self.process_id} step {self.step_number} {self.institute_code or self.custom_name}"


class DuplicateOverride(SoftDeleteModel):
    """Auditable record of an admin clearing a fired duplicate warning (§5.7)."""

    class MatchReason(models.TextChoices):
        PID = "pid", "PID exact match"
        MOTHER_NAME = "mother_name", "Mother-name fuzzy match"

    process = models.ForeignKey(
        Process, on_delete=models.PROTECT, related_name="duplicate_overrides"
    )
    client = models.ForeignKey(
        "clients.Client", on_delete=models.PROTECT, related_name="duplicate_overrides"
    )
    match_reason = models.CharField(max_length=20, choices=MatchReason.choices)
    overridden_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    reason = models.TextField()

    class Meta:
        db_table = "duplicate_override"

    def __str__(self):
        return f"Override p#{self.process_id} ({self.match_reason})"
