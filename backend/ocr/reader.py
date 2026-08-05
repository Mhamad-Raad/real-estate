"""Tesseract access — the only module that touches the engine or the filesystem (§6.5).

Kept separate from `extraction` so the parsing rules stay pure and unit-testable without an OCR
install. Two deliberate choices, both measured during the accuracy spike:

* **Each side is read twice, with a different model per script.** The Arabic script model reads
  Sorani names well but mangles Latin digits (the card number came back as `240M 01`); `eng`
  reads the digits and the MRZ cleanly but cannot see Arabic at all. Reading once with either
  loses half the card — and the digits pass is what makes the front/MRZ cross-check possible.
* **The raw image is used as-is — there is deliberately no cleanup path here.** Thresholding a
  modern glossy card shredded the thin Arabic strokes and produced far worse output. Re-measured
  against *photocopied* input (§6.2), denoise+CLAHE+threshold rescued nothing and at two copier
  generations destroyed a card number the raw read had recovered. Degraded scans are handled by
  the check digits reporting the failure, not by trying to repair the pixels.

**Second-chance pass (2026-08-04).** A card photographed to fill the frame reads well under
Tesseract's automatic page segmentation. A card *scanned onto a sheet of paper* does not: the
content is a small island on a mostly-blank page and the automatic mode returns almost nothing —
measured 0 characters on a real office scan. Framing the content and asking for a uniform block
instead recovered ~1,400. **It is a fallback, not a replacement:** the same settings applied to a
photographed card destroy it outright (5 fields → 0, measured). So the ordinary read runs first
and this only runs when it came back with nothing usable, and the better of the two drafts wins.
"""

from dataclasses import dataclass
from pathlib import Path

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


# What the enlargement is aiming at: a cropped card whose longest edge is about this many pixels
# reads well. Enlarging past it buys nothing and costs a great deal — Tesseract's layout analysis
# is superlinear, so doubling a full page took **27.8s** against 2.4s for the page itself (UC-065).
FRAMED_TARGET_LONG_EDGE = 2200
MAX_FRAME_SCALE = 2.0

# An ID card is 85.6 × 54 mm — about 1.59 either way up. The rescue below is only worth its cost
# on something card-shaped; a scan of a full A4 page crops to roughly 0.4, and running the
# expensive pass on it found **nothing at all** while taking 24 seconds (UC-065).
CARD_ASPECT_RANGE = (1.15, 2.30)


def looks_like_a_card(image) -> bool:
    """Is this framed region shaped like an ID card, either orientation?

    Anything without real dimensions answers **yes**: this gate only ever *withholds* the
    expensive rescue, so when it cannot tell it must not be the thing that suppresses a reading.
    """
    size = getattr(image, "size", None)
    if not size or min(size) <= 0:
        return True
    return CARD_ASPECT_RANGE[0] <= max(size) / min(size) <= CARD_ASPECT_RANGE[1]


# A scan puts the card on a sheet: frame the ink and enlarge it, so the engine is handed the card
# rather than a page that is mostly paper. Only ever used by the second-chance pass below.
def frame_content(image, *, threshold: int = 190, pad: int = 30):
    import numpy as np
    from PIL import Image

    grey = np.asarray(image.convert("L"))
    ink = grey < threshold
    rows = np.where(ink.sum(axis=1) > 3)[0]
    cols = np.where(ink.sum(axis=0) > 3)[0]
    if len(rows) and len(cols):
        height, width = grey.shape
        image = image.crop(
            (
                max(0, int(cols[0]) - pad),
                max(0, int(rows[0]) - pad),
                min(width, int(cols[-1]) + pad),
                min(height, int(rows[-1]) + pad),
            )
        )
    # Enlarge only what is actually small. The whole point is a card occupying a corner of a
    # sheet; when the ink already fills the page there is nothing to rescue by making it bigger,
    # and a blanket ×2 was what turned an import into a ten-minute wait (UC-065).
    scale = min(MAX_FRAME_SCALE, FRAMED_TARGET_LONG_EDGE / max(image.width, image.height))
    if scale <= 1.05:
        return image
    return image.resize((round(image.width * scale), round(image.height * scale)), Image.LANCZOS)


def read_side(image, *, psm: int | None = None) -> SideRead:
    """Read one side with both models, and report how sure the engine was about long digit runs."""
    import pytesseract
    from pytesseract import Output

    # The same `config` on every pass. The two `image_to_data` calls used to run without it, so
    # the confidence figures came from a different page-segmentation mode than the text they were
    # meant to describe — and paid for a second, more expensive layout analysis to do it.
    config = f"--psm {psm}" if psm else ""
    result = SideRead(
        arabic_text=pytesseract.image_to_string(image, lang=ARABIC_MODEL, config=config),
        latin_text=pytesseract.image_to_string(image, lang=LATIN_MODEL, config=config),
    )
    data = pytesseract.image_to_data(
        image, lang=LATIN_MODEL, config=config, output_type=Output.DICT
    )
    confidences = [
        int(conf)
        for text, conf in zip(data["text"], data["conf"])
        if text.strip().isdigit() and len(text.strip()) >= 10 and str(conf).lstrip("-").isdigit()
    ]
    result.digit_confidence = max(confidences) if confidences else 0

    # Names carry no check digit, so the engine's own confidence is the only signal the verify
    # screen has for "look at this one closely".
    arabic = pytesseract.image_to_data(
        image, lang=ARABIC_MODEL, config=config, output_type=Output.DICT
    )
    word_confidences = [
        int(conf)
        for text, conf in zip(arabic["text"], arabic["conf"])
        if text.strip() and str(conf).lstrip("-").isdigit() and int(conf) >= 0
    ]
    result.name_confidence = (
        round(sum(word_confidences) / len(word_confidences)) if word_confidences else 0
    )
    return result


def _filled(draft: IdCardDraft) -> int:
    """How many fields the reading actually produced — the score the two passes compete on."""
    return sum(
        1
        for name in ("pid", "full_name", "mother_full_name", "date_of_birth", "sex")
        if str(getattr(getattr(draft, name, None), "value", "") or "").strip()
    )


def _read_pair(front_image, back_image, *, psm: int | None, framed: bool):
    prepare = frame_content if framed else (lambda image: image)
    front = read_side(prepare(front_image), psm=psm)
    back = read_side(prepare(back_image), psm=psm) if back_image is not None else SideRead()
    draft = build_draft(
        # Names come from the Arabic pass, the card number from the Latin one — concatenating
        # them lets a single regex find the digits without disturbing the positional name parse.
        front_text=front.arabic_text,
        front_latin_text=front.latin_text,
        back_text=back.latin_text,
        pid_confidence=front.digit_confidence,
        name_confidence=front.name_confidence,
    )
    return draft, front


def read_card(front_path: Path, back_path: Path | None = None) -> IdCardDraft:
    """Read one or both sides of a card into a draft.

    The back is optional: a lawyer may photograph only the front. Without it there is no MRZ, so
    the dates lose their check digits and the draft says so rather than quietly looking certain.
    """
    front_images = load_images(front_path)
    back_image = None
    if back_path is not None:
        back_image = load_images(back_path)[0]
    elif len(front_images) > 1:
        # A two-page PDF is the usual shape when both sides are scanned into one file.
        back_image = front_images[1]

    draft, front = _read_pair(front_images[0], back_image, psm=None, framed=False)

    # A card scanned onto a sheet of paper defeats the automatic segmentation entirely. Retry it
    # framed, and keep that reading ONLY if it found more — the same settings ruin a photographed
    # card, so this may never become the default.
    #
    # Attempted only when the framed region is actually card-shaped. `--psm 6` costs ~10× the
    # automatic segmentation, and on a scan of a full page — which crops to a page, not a card —
    # it spent that on finding nothing, turning an import into a wait long enough that the office
    # gave up and typed the details by hand (UC-065). A page still gets the plain read above; what
    # it no longer gets is minutes of a pass that cannot help it.
    if _filled(draft) == 0 and looks_like_a_card(frame_content(front_images[0])):
        rescued, rescued_front = _read_pair(front_images[0], back_image, psm=6, framed=True)
        if _filled(rescued) > _filled(draft):
            rescued.warnings.append(
                "This looked like a scan of a page rather than a photograph of the card, so it was "
                "read a second time. Check every field before confirming."
            )
            return rescued

    if not front.is_readable:
        draft.warnings.insert(0, "The front of the card could not be read. Enter the details by hand.")
    return draft
