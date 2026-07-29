"""The OCR draft that sits between a scan and a saved client record (§6.5).

Status lives in the database, not Celery's result backend: it survives a broker restart, it is
what the verify screen polls, and a failure keeps its reason instead of vanishing.

The draft is deliberately *not* the client record. OCR proposes; a human confirms; only then is
anything written to `Client` — and confirming does not freeze the data, since every field stays
editable afterwards through the normal audited edit path.
"""

from django.conf import settings
from django.db import models

from common.models import TimeStampedModel


class OcrRun(TimeStampedModel):
    """One reading of one document."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        DONE = "done", "Done"
        FAILED = "failed", "Failed"

    document = models.ForeignKey(
        "documents.Document", on_delete=models.PROTECT, related_name="ocr_runs"
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    # `{"fields": {name: {value, confidence, source, verified}}, "warnings": [...]}` — the shape
    # `extraction.IdCardDraft.as_dict()` produces, stored verbatim so the verify screen and any
    # later audit see exactly what the engine proposed.
    draft = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    # Set when a human accepts the draft. Kept on the run, not just the client, so the trail shows
    # which reading was confirmed and by whom — the run itself is never edited afterwards.
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )

    class Meta:
        db_table = "ocr_run"
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["document", "-created_at"], name="ix_ocr_document")]

    def __str__(self):
        return f"OCR #{self.pk} of document {self.document_id} ({self.status})"
