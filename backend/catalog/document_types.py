"""The ONE definition of the controlled document types (§6.7).

`Document.document_type` stores these machine codes; `processes.status` derives which ones a step
still needs; the frontend fetches them read-only via GET /api/v1/document-types/ to lay out its
upload slots. Keeping the list here means a step can never require a document the UI offers no
slot for. Display names are i18n keys, so the code stays stable in the DB while ckb/ar/en labels
come from the translation files.

The vocabulary is deliberately partial — steps 2–4 use the generic `InstituteDoc`, and generated
types (EligibilityBase, spouse PDFs) land with Iteration 3 (§0).
"""

# (code, i18n display key, step, required for that step's completion)
DOCUMENT_TYPES: list[tuple[str, str, int, bool]] = [
    ("ClientID", "workflow.docType.ClientID", 1, True),
    ("RealEstate", "workflow.docType.RealEstate", 1, True),
    ("SignedAgreement", "workflow.docType.SignedAgreement", 1, True),
    # Steps 2–4 attach one generic document per institute entry, not a fixed named set.
    ("InstituteDoc", "workflow.docType.InstituteDoc", None, False),
]

DOCUMENT_TYPE_CODES = frozenset(code for code, _key, _step, _req in DOCUMENT_TYPES)


def required_codes_for_step(step: int) -> tuple[str, ...]:
    """Codes a step must have on file to count as complete (§3.6). Ordered — it is rendered."""
    return tuple(code for code, _key, s, required in DOCUMENT_TYPES if s == step and required)


def document_types_as_dicts() -> list[dict]:
    return [
        {"code": code, "display_key": key, "step": step, "required": required}
        for code, key, step, required in DOCUMENT_TYPES
    ]
