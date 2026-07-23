"""Document — a PDF attached to a process (§6.7). Scanned/imported/generated all share this row."""

from django.conf import settings
from django.db import models

from common.models import SoftDeleteModel


class Document(SoftDeleteModel):
    class InputSource(models.TextChoices):
        SCANNED = "scanned", "Scanned"
        IMPORTED = "imported", "Imported"
        SYSTEM_GENERATED = "system_generated", "System generated"

    class OcrStatus(models.TextChoices):
        NA = "na", "N/A"
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        DONE = "done", "Done"
        FAILED = "failed", "Failed"

    class VerificationStatus(models.TextChoices):
        NA = "na", "N/A"
        PENDING = "pending", "Pending"
        VERIFIED = "verified", "Verified"

    process = models.ForeignKey(
        "processes.Process", on_delete=models.PROTECT, related_name="documents"
    )
    step_number = models.PositiveSmallIntegerField()
    document_type = models.CharField(max_length=60)  # controlled label (ClientID, SignedAgreement…)
    # Set for Step 2–4 per-institute uploads; null for Step-1 client papers & generated PDFs.
    institute_entry = models.ForeignKey(
        "processes.ProcessInstituteEntry",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="documents",
    )
    input_source = models.CharField(max_length=20, choices=InputSource.choices)
    ocr_status = models.CharField(max_length=12, choices=OcrStatus.choices, default=OcrStatus.NA)
    verification_status = models.CharField(
        max_length=12, choices=VerificationStatus.choices, default=VerificationStatus.NA
    )
    file_path = models.CharField(max_length=300)  # relative to DOCUMENTS_ROOT — the authoritative pointer
    display_filename = models.CharField(max_length=200)
    sha256 = models.CharField(max_length=64)
    original_filename = models.CharField(max_length=255, blank=True)
    size_bytes = models.PositiveIntegerField(default=0)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )

    class Meta:
        db_table = "document"
        indexes = [
            # Per-step document-presence checks that drive step status (§3.6).
            models.Index(
                fields=["process", "step_number"],
                name="ix_doc_process_step",
                condition=models.Q(is_deleted=False),
            ),
        ]

    def __str__(self):
        return self.display_filename
