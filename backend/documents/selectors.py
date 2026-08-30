"""Read/query logic for documents (§3.6 presence checks, §4.2)."""

from django.db.models import Sum

from .models import Document


def documents_for_process(process_id, step_number=None):
    qs = Document.objects.filter(process_id=process_id).select_related("institute_entry")
    if step_number is not None:
        qs = qs.filter(step_number=step_number)
    return qs.order_by("step_number", "created_at")


def slot_usage(*, process_id, step_number, document_type, institute_entry_id=None, by_pages=False):
    """How much of one upload slot is already filed — pages for a card, rows for everything else.

    Scoped by `institute_entry` as well as by type: steps 2–4 file the same generic `InstituteDoc`
    once per institute, so counting them process-wide would call the second institute's slot full.
    Soft-deleted rows are excluded by the default manager, which is what lets a lawyer make room by
    deleting the wrong scan.
    """
    qs = Document.objects.filter(
        process_id=process_id,
        step_number=step_number,
        document_type=document_type,
        institute_entry_id=institute_entry_id,
    )
    if by_pages:
        return qs.aggregate(pages=Sum("page_count"))["pages"] or 0
    return qs.count()
