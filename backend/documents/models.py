"""Document — a PDF attached to a process (§6.7). Scanned/imported/generated all share this row."""

from django.conf import settings
from django.db import models

from catalog import document_types

from common.models import JobStatus, SoftDeleteModel, TimeStampedModel


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
    # Pages in the stored PDF, recorded at upload (UC-083). An ID card is deliberately ONE
    # document holding both sides (`ocr.services.stage_scan`), so "how many sides are on file"
    # cannot be answered by counting rows — and counting them made a complete card report
    # "1 of 2 files". Stored rather than derived: the slot renders on every case load, and
    # opening each PDF to count its pages would be a file read per document per request.
    page_count = models.PositiveSmallIntegerField(default=0)
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

    @property
    def is_scanned_case_file(self) -> bool:
        """The paper case file the backlog door carried in (§5.9, UC-114) — the only copy.

        Same type as the export the app used to store, opposite meaning: that one was rebuilt on
        every press, this one cannot be. Every rule that treats the two differently asks here.
        """
        return (
            self.document_type == document_types.COMPILED_CASE
            and self.input_source != self.InputSource.SYSTEM_GENERATED
        )


class DocumentTemplate(SoftDeleteModel):
    """A stored office form (§3.5, §6.6). Two kinds, and the difference is load-bearing.

    Most are `.docx` **letters the system fills in**: `docxtpl` renders them per case, so the shape
    of a letter is data, not code. `REQUEST_FORM` is the other kind — a **blank form the office
    prints, has signed and scans back** as the optional `Request` document (UC-039). It carries no
    placeholders and is stored as the PDF the office supplied, so what goes on paper is their own
    file rather than a re-render of it.
    """

    class TemplateType(models.TextChoices):
        ELIGIBILITY_SINGLE = "eligibility_single", "Eligibility letter (one beneficiary)"
        PROCESS_LIST = "process_list", "Beneficiary list letter"
        CASE_SUMMARY = "case_summary", "Compiled case summary (Step 5)"
        PROCESS_CODES = "process_codes", "Beneficiary code list"
        REQUEST_FORM = "request_form", "Request form (blank, for printing)"

    # The types the system never fills in. Named once here because three call sites branch on it —
    # what a valid upload is, what `preview` returns, and what generation refuses to touch.
    BLANK_FORM_TYPES = frozenset({TemplateType.REQUEST_FORM})

    @property
    def is_blank_form(self) -> bool:
        return self.template_type in self.BLANK_FORM_TYPES

    template_type = models.CharField(max_length=32, choices=TemplateType.choices)
    name = models.CharField(max_length=120)
    file_path = models.CharField(max_length=300)  # relative to LETTER_TEMPLATES_ROOT
    original_filename = models.CharField(max_length=255, blank=True)
    sha256 = models.CharField(max_length=64)
    size_bytes = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )

    class Meta:
        db_table = "document_template"
        constraints = [
            # Generation looks up "the" template for a type, so exactly one may be active.
            models.UniqueConstraint(
                fields=["template_type"],
                condition=models.Q(is_active=True, is_deleted=False),
                name="ix_template_active_per_type",
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.template_type})"


class GenerationJob(TimeStampedModel):
    """One template→PDF run (§6.6, §6.8). Lifecycle rules live on `JobStatus`."""

    class Kind(models.TextChoices):
        ELIGIBILITY = "eligibility", "Eligibility letter"
        PROCESS_LIST = "process_list", "Beneficiary list"
        COMPILED_CASE = "compiled_case", "Compiled case export"
        PROCESS_CODES = "process_codes", "Beneficiary code list"

    # Aliased so every existing `GenerationJob.Status.*` caller keeps working.
    Status = JobStatus

    kind = models.CharField(max_length=20, choices=Kind.choices)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    template = models.ForeignKey(DocumentTemplate, on_delete=models.PROTECT, related_name="jobs")
    # Set for a single-beneficiary letter; the list letter spans many, so it records their ids.
    process = models.ForeignKey(
        "processes.Process", null=True, blank=True, on_delete=models.PROTECT, related_name="jobs"
    )
    process_ids = models.JSONField(default=list, blank=True)
    document = models.ForeignKey(
        Document, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    # A list letter spans several people, so it does not belong in any one person's folder (§6.8).
    output_path = models.CharField(max_length=300, blank=True)
    error = models.TextField(blank=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )

    class Meta:
        db_table = "generation_job"
        indexes = [models.Index(fields=["process", "kind"], name="ix_job_process_kind")]

    def __str__(self):
        return f"{self.kind} #{self.pk} ({self.status})"
