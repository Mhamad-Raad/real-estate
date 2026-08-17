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
    # How many parts the office files here — the slot's **capacity**, enforced on upload (UC-085).
    # It is not a *completion* rule in the other direction: a slot short of its second part still
    # counts as present, so a step is never blocked on it (UC-055).
    expected_parts: int = 1
    # **What a "part" is.** For most papers it is a file, one row each. An identity card is not:
    # both sides are deliberately stored as ONE document with two pages
    # (`ocr.services.stage_scan`), so counting rows told the office that a complete card was
    # "1 of 2 files" (UC-083). Those slots count pages instead, and say "sides".
    counts_pages: bool = False


# The two identity papers. Named because OCR reads these into client fields and files the rest
# (§6.5) — the codes belong here with the rest of the vocabulary, not as literals in the ocr app.
CLIENT_ID = "ClientID"
SPOUSE_ID = "SpouseID"
IDENTITY_TYPE_CODES = (CLIENT_ID, SPOUSE_ID)

# Named for the same reason: the blank `request_form` template the office prints is the blank of
# *this* paper, and it takes its download name from here rather than inventing a second one (§6.6).
REQUEST = "Request"

# The two system outputs. Named here with the rest of the vocabulary because both are *excluded*
# from the compiled export and the exclusion has to name them: the previous compilation, or each
# run would nest the last inside the next, and the eligibility letter, which the office does not
# want in the compilation (UC-075). Nothing files a letter any more — cases opened before that
# change still carry one, which is exactly why the code must stay declared.
ELIGIBILITY_LETTER = "EligibilityLetter"
COMPILED_CASE = "CompiledCase"

# An identity card has two sides, and a case typed in by hand arrives with them as two separate
# scans (UC-080). The scan-capture path merges the pair into one PDF, so plenty of existing cases
# hold a single file here — the count is a hint and never blocks a step (UC-055), so both shapes
# are fine. Declared once because both cards are filed the same way.
ID_CARD_SIDES = 2

DOCUMENT_TYPES: list[DocumentType] = [
    DocumentType(
        CLIENT_ID, "workflow.docType.ClientID", 1, True,
        expected_parts=ID_CARD_SIDES, counts_pages=True,
    ),
    DocumentType(
        SPOUSE_ID, "workflow.docType.SpouseID", 1, True,
        only_when_married=True, expected_parts=ID_CARD_SIDES, counts_pages=True,
    ),
    # Produced by the Step-4 registration institutes, so it cannot be demanded when a case opens
    # (UC-037). Step 4 is the first institute step that also carries a named-document requirement.
    # The office files it as two papers (UC-055).
    DocumentType("RealEstate", "workflow.docType.RealEstate", 4, True, expected_parts=2),
    DocumentType("SignedAgreement", "workflow.docType.SignedAgreement", 1, True),
    # The citizen's own request. Optional on purpose — not every case arrives with one, so it must
    # never hold Step 1 back. The office prints the blank form, has it signed, and scans it back,
    # which is why it is an upload slot and not a `generated` output like the letter below.
    DocumentType(REQUEST, "workflow.docType.Request", 1, False),
    DocumentType(
        ELIGIBILITY_LETTER, "workflow.docType.EligibilityLetter", 1, False, generated=True
    ),
    # Steps 2–4 attach one generic document per institute entry, not a fixed named set.
    DocumentType("InstituteDoc", "workflow.docType.InstituteDoc", None, False),
    # The Step-5 compiled export: system output, never an upload slot (§10.3).
    DocumentType(COMPILED_CASE, "workflow.docType.CompiledCase", 5, False, generated=True),
]

DOCUMENT_TYPE_CODES = frozenset(dt.code for dt in DOCUMENT_TYPES)
_BY_CODE: dict[str, DocumentType] = {dt.code: dt for dt in DOCUMENT_TYPES}


def slot_capacity(code: str) -> tuple[int, bool]:
    """How much one slot may hold, and whether that is counted in **pages** or in **files** (§6.7).

    A card holds two sides in one document, so its capacity is pages; every other slot counts the
    papers filed under it. An unknown code gets the conservative single-file answer — the upload
    serializer refuses those anyway, so this only keeps the rule closed if that ever changes.
    """
    dt = _BY_CODE.get(code)
    return (dt.expected_parts, dt.counts_pages) if dt else (1, False)


# The Sorani names, for the **filenames** — the same reason `INSTITUTE_NAMES_CKB` exists. The
# office browses the document store by hand when the app is not in front of them, and it looks
# for these papers by the names it uses for them, not by `RealEstate` (UC-060).
DOCUMENT_TYPE_NAMES_CKB: dict[str, str] = {
    CLIENT_ID: "ناسنامەی کڕیار",
    SPOUSE_ID: "ناسنامەی هاوسەر",
    "RealEstate": "بەڵگەنامەی خانووبەرە",
    "SignedAgreement": "ڕێککەوتنی واژۆکراو",
    REQUEST: "داواکاری",
    "EligibilityLetter": "نامەی سۆراغکردنی سوودمەندی",
    "InstituteDoc": "بەڵگەنامەی دامەزراوە",
    "CompiledCase": "دۆسیەی کۆکراوەی کەیس",
}


def name_ckb(code: str) -> str:
    """The Sorani name for a type, falling back to the code so a file is never named blank."""
    return DOCUMENT_TYPE_NAMES_CKB.get(code, code or "")


def required_codes_for_step(step: int, *, married: bool = False) -> tuple[str, ...]:
    """Codes a step must have on file to count as complete (§3.6). Ordered — it is rendered."""
    return tuple(
        dt.code
        for dt in DOCUMENT_TYPES
        if dt.step == step and dt.required and (married or not dt.only_when_married)
    )


def document_types_as_dicts() -> list[dict]:
    return [dt._asdict() for dt in DOCUMENT_TYPES]
