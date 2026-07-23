"""Read/query logic for documents (§3.6 presence checks, §4.2)."""

from .models import Document


def documents_for_process(process_id, step_number=None):
    qs = Document.objects.filter(process_id=process_id).select_related("institute_entry")
    if step_number is not None:
        qs = qs.filter(step_number=step_number)
    return qs.order_by("step_number", "created_at")
