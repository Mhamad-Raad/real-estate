"""A card scan on its way to becoming a client record (§6.5, §6.7).

The scan arrives *before* the client exists: a lawyer photographs the ID, the engine reads it,
and the reading pre-fills the form that creates the person. So a scan is staged — written to disk
immediately (a photograph must never live only in a browser tab) but not yet filed under anyone's
folder, because the folder is keyed by the very PID and name the card is about to supply.

Confirmation is what makes it real: the client is created, the file moves into
`<CATEGORY>/<client_id>_<pid>/` under its composed name, and the document row is written verified.

The draft is deliberately *not* the client record. OCR proposes; a human confirms; only then is
anything written — and confirming does not freeze the data, since every field stays editable
afterwards through the normal audited edit path. Exactly one draft is kept per scan: re-reading
replaces it, and the record of what the engine proposed versus what the human accepted lives
permanently in the append-only audit log, not here.
"""

from django.conf import settings
from django.db import models

from common.models import JobStatus, TimeStampedModel


class CardScan(TimeStampedModel):
    """One photographed identity card, staged until a human confirms what it says."""

    Status = JobStatus

    # Which card this is — it decides whether the reading fills the client's own columns or the
    # spouse's. The same controlled vocabulary the rest of the document store uses.
    document_type = models.CharField(max_length=60)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    # `{"fields": {name: {value, confidence, source, verified}}, "warnings": [...]}` — the shape
    # `extraction.IdCardDraft.as_dict()` produces, stored verbatim so the review screen and the
    # audit trail see exactly what the engine proposed.
    draft = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)

    # Staging location, relative to DOCUMENTS_ROOT. Cleared once the file has been filed.
    file_path = models.CharField(max_length=300, blank=True)
    original_filename = models.CharField(max_length=255, blank=True)
    sha256 = models.CharField(max_length=64, blank=True)
    size_bytes = models.PositiveIntegerField(default=0)

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    # Set at confirmation — the filed document this scan became. Until then the scan is the only
    # thing that knows where the file is.
    document = models.ForeignKey(
        "documents.Document", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    # Set by the sweep when a scan was abandoned: the staged image of someone's ID is deleted, but
    # the row stays so the audit trail still shows a card was read and never became a record.
    discarded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "card_scan"
        ordering = ("-created_at",)
        indexes = [
            # Finding the scans a lawyer started but never confirmed (review screen, cleanup).
            models.Index(fields=["uploaded_by", "-created_at"], name="ix_scan_uploader"),
            models.Index(
                fields=["-created_at"],
                name="ix_scan_unconfirmed",
                condition=models.Q(confirmed_at__isnull=True),
            ),
        ]

    def __str__(self):
        return f"Card scan #{self.pk} ({self.document_type}, {self.status})"

    @property
    def is_confirmed(self) -> bool:
        return self.confirmed_at is not None
