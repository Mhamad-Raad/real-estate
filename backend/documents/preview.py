"""Render a letter template to PDF with sample data, so the Templates screen can show the letter.

The screen used to show only a filename and a size, which says nothing about what the office is
about to send (§6.6, UC-010). Rendering the *blank* template was the obvious alternative and is
worse: empty gaps and an empty beneficiary table read as a broken document rather than as "this is
the letter", so every value here is deliberately marked as a sample.
"""

import tempfile
from pathlib import Path

from processes.constants import STEP_NUMBERS

from .generation import render_to_pdf
from .letters import to_arabic_indic
from .models import DocumentTemplate
from .summary import LABELS

# Obviously-not-real values. A preview must never be mistaken for a real beneficiary's letter, and
# these also exercise the layout the office cares about: a long name, and a married row beside an
# unmarried one whose spouse cells stay blank.
SAMPLE_ROWS = [
    {
        "n": to_arabic_indic(1),
        "full_name": "نموونە — ناوی سوودمەند",
        "year": to_arabic_indic(1990),
        "mother_name": "نموونە — ناوی دایک",
        "spouse_name": "نموونە — ناوی هاوسەر",
        "spouse_year": to_arabic_indic(1992),
        "spouse_mother_name": "نموونە — دایکی هاوسەر",
    },
    {
        "n": to_arabic_indic(2),
        "full_name": "نموونە — سوودمەندی دووەم",
        "year": to_arabic_indic(1985),
        "mother_name": "نموونە — دایکی دووەم",
        "spouse_name": "",
        "spouse_year": "",
        "spouse_mother_name": "",
    },
]


def _sample_context(template_type: str) -> dict:
    """The same context shape each real job builds, so a preview cannot drift from the output."""
    rows = SAMPLE_ROWS[:1] if template_type == DocumentTemplate.TemplateType.ELIGIBILITY_SINGLE else SAMPLE_ROWS
    if template_type == DocumentTemplate.TemplateType.CASE_SUMMARY:
        # The cover sheet binds to a different contract (§10.3). Keys mirror `case_summary_context`
        # exactly — a preview that invented its own keys would render blanks and look broken.
        return {
            "client_name": SAMPLE_ROWS[0]["full_name"],
            "client_pid": to_arabic_indic("200000000000"),
            "mother_name": SAMPLE_ROWS[0]["mother_name"],
            "birth_year": SAMPLE_ROWS[0]["year"],
            # The sample beneficiary carries spouse values, so the status must say so — pulling a
            # step label in here printed "complete" where the letter shows a marital status.
            "marital_status": LABELS["married"],
            "spouse_name": SAMPLE_ROWS[0]["spouse_name"],
            "land_id": "نموونە — L-1",
            "land_address": "نموونە — ناونیشان",
            "category": "نموونە",
            "overall_status": LABELS["in_progress"],
            "assigned_lawyer": "نموونە",
            "created_at": to_arabic_indic("2026-01-01"),
            "steps": [
                {
                    "n": to_arabic_indic(n),
                    "status": LABELS["complete"],
                    "start_date": "",
                    "end_date": "",
                }
                for n in STEP_NUMBERS
            ],
            "institutes": [],
            "document_count": to_arabic_indic(0),
        }
    return {
        "rows": rows,
        "count": to_arabic_indic(len(rows)),
        "first_name": rows[0]["full_name"],
        "last_name": rows[-1]["full_name"],
    }


def render_template_preview(template: DocumentTemplate) -> bytes:
    """PDF bytes for this template, filled with sample values. Raises `RenderError` on failure."""
    with tempfile.TemporaryDirectory() as tmp:
        return render_to_pdf(template, _sample_context(template.template_type), Path(tmp))
