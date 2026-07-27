"""The ONE definition of the controlled document types (§6.7).

`Document.document_type` stores these machine codes; `processes.status` derives which ones a step
still needs; the frontend fetches them read-only via GET /api/v1/document-types/ to lay out its
upload slots. Keeping the list here means a step can never require a document the UI offers no
slot for. Display names are i18n keys, so the code stays stable in the DB while ckb/ar/en labels
come from the translation files.

The vocabulary is deliberately partial — steps 2–4 use the generic `InstituteDoc`, and generated
types (the eligibility letter) land with Iteration 3 (§0).
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


DOCUMENT_TYPES: list[DocumentType] = [
    DocumentType("ClientID", "workflow.docType.ClientID", 1, True),
    DocumentType("SpouseID", "workflow.docType.SpouseID", 1, True, only_when_married=True),
    DocumentType("RealEstate", "workflow.docType.RealEstate", 1, True),
    DocumentType("SignedAgreement", "workflow.docType.SignedAgreement", 1, True),
    # Steps 2–4 attach one generic document per institute entry, not a fixed named set.
    DocumentType("InstituteDoc", "workflow.docType.InstituteDoc", None, False),
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
