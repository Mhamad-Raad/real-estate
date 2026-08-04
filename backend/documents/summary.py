"""Context builder for the Step-5 compiled case summary (§10.3).

Pure function: a process in, a plain dict out. Like `letters.py` this dict is the **contract**
the summary `.docx` binds to, so the office can restyle the cover sheet in Word without any
code change.
"""

from catalog.institutes import INSTITUTES, name_ckb

from .letters import to_arabic_indic

STEP_NUMBERS = (1, 2, 3, 4, 5)
DISPLAY_KEYS = {code: key for code, key, _step in INSTITUTES}

# The generated documents are Kurdish government paperwork — the letters are written in Sorani
# and so is this cover sheet. Status codes are therefore translated here rather than shipped as
# raw machine values like "not_started", which would be meaningless on a signed export.
LABELS = {
    "not_started": "دەست پێنەکراوە",
    "in_progress": "لە پرۆسەدایە",
    "missing": "بەڵگەنامەی کەم",
    "complete": "تەواو",
    "draft": "ڕەشنووس",
    "rejected": "ڕەتکراوە",
    "pending": "چاوەڕوانی",
    "approved": "پەسەندکراو",
    "single": "سەڵت",
    "married": "خێزاندار",
    "divorced": "جیابووەوە",
    "widowed": "بێوەژن",
}


def _label(code: str) -> str:
    """Fall back to the raw code rather than blanking an untranslated value."""
    return LABELS.get(code, code or "")


def _date(value) -> str:
    return to_arabic_indic(value.isoformat()) if value else ""


def _institute_rows(process) -> list[dict]:
    """Every institute touched by steps 2–4, in step order then insertion order.

    Custom (out-of-city) entries carry a free-text name instead of a catalogue code, so the
    display name has to fall back to it rather than to an enum lookup.
    """
    rows = []
    for entry in sorted(
        process.institute_entries.all(), key=lambda e: (e.step_number, e.id)
    ):
        rows.append(
            {
                "step": to_arabic_indic(entry.step_number),
                # The Sorani name, not the machine code: this is printed on a signed document
                # (UC-058). A custom out-of-city row has no code, so its free text stands.
                "name": entry.custom_name if entry.is_custom else name_ckb(entry.institute_code),
                # The i18n key so the summary can be localised; blank for custom entries,
                # whose name is free text the office typed and must print verbatim.
                "label_key": "" if entry.is_custom else DISPLAY_KEYS.get(entry.institute_code, ""),
                "is_custom": entry.is_custom,
                "approval_status": _label(entry.approval_status),
                "approval_date": _date(entry.approval_date),
                "lawyer": entry.assigned_lawyer.username if entry.assigned_lawyer else "",
            }
        )
    return rows


def _step_rows(process) -> list[dict]:
    by_number = {step.step_number: step for step in process.steps.all()}
    return [
        {
            "n": to_arabic_indic(number),
            "status": _label(by_number[number].status) if number in by_number else "",
            "start_date": _date(by_number[number].start_date) if number in by_number else "",
            "end_date": _date(by_number[number].end_date) if number in by_number else "",
        }
        for number in STEP_NUMBERS
    ]


def case_summary_context(process, attachments) -> dict:
    """Everything the compiled cover sheet prints about one allocation.

    `attachments` is the exact list that will be merged after this cover sheet. It is passed in
    rather than recomputed because `process.documents` still contains the *previous* compiled
    export at this point — counting that would print a document total one higher than the file
    actually contains, on a signed government document.
    """
    client = process.client

    return {
        "client_name": client.full_name,
        "client_pid": client.pid,
        "mother_name": client.mother_full_name,
        "birth_year": to_arabic_indic(client.date_of_birth.year) if client.date_of_birth else "",
        "marital_status": _label(client.marital_status),
        "spouse_name": client.spouse_name if client.is_married else "",
        "land_id": process.land_id,
        "land_address": process.land_address,
        "category": process.category.name if process.category else "",
        "overall_status": _label(process.overall_status),
        "assigned_lawyer": (
            process.assigned_lawyer.username if process.assigned_lawyer else ""
        ),
        "created_at": _date(process.created_at.date()),
        "steps": _step_rows(process),
        "institutes": _institute_rows(process),
        "document_count": to_arabic_indic(len(attachments)),
    }
