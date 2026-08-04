"""The ONE definition of the controlled document types (§6.7).

`Document.document_type` stores these machine codes; `processes.status` derives which ones a step
still needs; the frontend fetches them read-only via GET /api/v1/document-types/ to lay out its
upload slots. Keeping the list here means a step can never require a document the UI offers no
slot for. Display names are i18n keys, so the code stays stable in the DB while ckb/ar/en labels
come from the translation files.

The vocabulary is deliberately partial — steps 2–4 use the generic `InstituteDoc`, and the
generated type (the eligibility letter) is produced by the system, never uploaded.
"""

from typing import NamedTuple


class DocumentType(NamedTuple):
    code: str
    display_key: str
    step: int | None
    required: bool
    # Some papers only exist when there is a spouse; the condition belongs to the type itself so
    # the backend requirement and the frontend upload slot can never disagree.
    only_when_married: bool = False
    # Produced by the system (§6.6) — shown as output, never offered as an upload slot.
    generated: bool = False
    # How many files the office expects in this slot. Drives the UI hint only — completion still
    # asks whether the type is present at all, so a slot short of its second file is not blocked.
    expected_files: int = 1


# The two identity papers. Named because OCR reads these into client fields and files the rest
# (§6.5) — the codes belong here with the rest of the vocabulary, not as literals in the ocr app.
CLIENT_ID = "ClientID"
SPOUSE_ID = "SpouseID"
IDENTITY_TYPE_CODES = (CLIENT_ID, SPOUSE_ID)

DOCUMENT_TYPES: list[DocumentType] = [
    DocumentType(CLIENT_ID, "workflow.docType.ClientID", 1, True),
    DocumentType(SPOUSE_ID, "workflow.docType.SpouseID", 1, True, only_when_married=True),
    # Produced by the Step-4 registration institutes, so it cannot be demanded when a case opens
    # (UC-037). Step 4 is the first institute step that also carries a named-document requirement.
    # The office files it as two papers (UC-055).
    DocumentType("RealEstate", "workflow.docType.RealEstate", 4, True, expected_files=2),
    DocumentType("SignedAgreement", "workflow.docType.SignedAgreement", 1, True),
    DocumentType(
        "EligibilityLetter", "workflow.docType.EligibilityLetter", 1, False, generated=True
    ),
    # Steps 2–4 attach one generic document per institute entry, not a fixed named set.
    DocumentType("InstituteDoc", "workflow.docType.InstituteDoc", None, False),
    # The Step-5 compiled export: system output, never an upload slot (§10.3).
    DocumentType("CompiledCase", "workflow.docType.CompiledCase", 5, False, generated=True),
]

DOCUMENT_TYPE_CODES = frozenset(dt.code for dt in DOCUMENT_TYPES)


def required_codes_for_step(step: int, *, married: bool = False) -> tuple[str, ...]:
    """Codes a step must have on file to count as complete (§3.6). Ordered — it is rendered."""
    return tuple(
        dt.code
        for dt in DOCUMENT_TYPES
        if dt.step == step and dt.required and (married or not dt.only_when_married)
    )


def document_types_as_dicts() -> list[dict]:
    return [dt._asdict() for dt in DOCUMENT_TYPES]
