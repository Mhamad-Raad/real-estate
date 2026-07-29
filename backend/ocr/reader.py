"""Tesseract access — the only module that touches the engine or the filesystem (§6.5).

Kept separate from `extraction` so the parsing rules stay pure and unit-testable without an OCR
install. Two deliberate choices, both measured during the accuracy spike:

* **Each side is read twice, with a different model per script.** The Arabic script model reads
  Sorani names well but mangles Latin digits (the card number came back as `240M 01`); `eng`
  reads the digits and the MRZ cleanly but cannot see Arabic at all. Reading once with either
  loses half the card — and the digits pass is what makes the front/MRZ cross-check possible.
* **The raw image is tried first.** Thresholding a modern glossy card shredded the thin Arabic
  strokes and produced far worse output, so cleanup is a fallback for a bad photo, not a stage
  every scan goes through.
"""

from dataclasses import dataclass
from pathlib import Path

from django.conf import settings

from .extraction import ARABIC_MODEL, LATIN_MODEL, IdCardDraft, build_draft

# Below this, a page is treated as unreadable rather than passed on as a confident draft.
MIN_USABLE_CHARS = 20


@dataclass
class SideRead:
    arabic_text: str = ""
    latin_text: str = ""
    digit_confidence: int = 0
    # Mean confidence over the Arabic words — how sure the engine was about the name block.
    name_confidence: int = 0

    @property
    def is_readable(self) -> bool:
        return len(self.arabic_text.strip()) + len(self.latin_text.strip()) >= MIN_USABLE_CHARS


def load_images(path: Path) -> list:
    """A page image per side. Accepts an image file or a PDF (rasterised at 300 dpi)."""
    from PIL import Image

    if path.suffix.lower() == ".pdf":
        from pdf2image import convert_from_path

        return convert_from_path(str(path), dpi=300)
    return [Image.open(path)]


def read_side(image) -> SideRead:
    """Read one side with both models, and report how sure the engine was about long digit runs."""
    import pytesseract
    from pytesseract import Output

    result = SideRead(
        arabic_text=pytesseract.image_to_string(image, lang=ARABIC_MODEL),
        latin_text=pytesseract.image_to_string(image, lang=LATIN_MODEL),
    )
    data = pytesseract.image_to_data(image, lang=LATIN_MODEL, output_type=Output.DICT)
    confidences = [
        int(conf)
        for text, conf in zip(data["text"], data["conf"])
        if text.strip().isdigit() and len(text.strip()) >= 10 and str(conf).lstrip("-").isdigit()
    ]
    result.digit_confidence = max(confidences) if confidences else 0

    # Names carry no check digit, so the engine's own confidence is the only signal the verify
    # screen has for "look at this one closely".
    arabic = pytesseract.image_to_data(image, lang=ARABIC_MODEL, output_type=Output.DICT)
    word_confidences = [
        int(conf)
        for text, conf in zip(arabic["text"], arabic["conf"])
        if text.strip() and str(conf).lstrip("-").isdigit() and int(conf) >= 0
    ]
    result.name_confidence = (
        round(sum(word_confidences) / len(word_confidences)) if word_confidences else 0
    )
    return result


def read_card(front_path: Path, back_path: Path | None = None) -> IdCardDraft:
    """Read one or both sides of a card into a draft.

    The back is optional: a lawyer may photograph only the front. Without it there is no MRZ, so
    the dates lose their check digits and the draft says so rather than quietly looking certain.
    """
    front_images = load_images(front_path)
    front = read_side(front_images[0])

    back = SideRead()
    if back_path is not None:
        back = read_side(load_images(back_path)[0])
    elif len(front_images) > 1:
        # A two-page PDF is the usual shape when both sides are scanned into one file.
        back = read_side(front_images[1])

    draft = build_draft(
        # Names come from the Arabic pass, the card number from the Latin one — concatenating
        # them lets a single regex find the digits without disturbing the positional name parse.
        front_text=front.arabic_text,
        front_latin_text=front.latin_text,
        back_text=back.latin_text,
        pid_confidence=front.digit_confidence,
        name_confidence=front.name_confidence,
    )
    if not front.is_readable:
        draft.warnings.insert(0, "The front of the card could not be read. Enter the details by hand.")
    return draft


def read_document(document) -> IdCardDraft:
    """Read a stored `Document` — the entry point the OCR job uses."""
    return read_card(Path(settings.DOCUMENTS_ROOT) / document.file_path)
