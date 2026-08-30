"""Identity cards, four to a page, for the compiled export (§10.3, UC-081).

The office scans an ID card onto a **full A4/Letter page**, so a case with both sides of the
beneficiary's card and both sides of the spouse's contributed four near-empty pages to the
compiled file. They now share one sheet: client front and back on the first row, spouse front and
back on the second.

Two steps, and the first is what makes it worth doing. Placing four full pages into quadrants
would scale each to **0.44×**, leaving the card itself around half its real size on paper — on a
signed government document that is a worse outcome than the extra pages. So every page is first
cropped to the ink it actually carries; a card that fills its crop box is then scaled to fill a
quadrant, and comes out **larger** than it prints today.

Nothing here touches a stored document. The cards keep their own files exactly as scanned; this
composes a view of them for the export only.
"""

from io import BytesIO
from pathlib import Path

from django.conf import settings
from pypdf import PageObject, PdfReader, PdfWriter, Transformation

# A4 portrait, in points — the sheet the office prints on.
SHEET = (595.276, 841.890)
MARGIN = 28.0
GUTTER = 14.0
COLUMNS, ROWS = 2, 2
PER_SHEET = COLUMNS * ROWS

# Rasterising is only ever used to *find* the ink, never to draw it, so a coarse render is enough
# and keeps the pass cheap — the pages themselves stay vector.
DETECT_DPI = 50
# How dark a pixel must be to count as content. Scanner backgrounds are near-white but rarely
# pure white, and a threshold of 255 would treat every speck of paper grain as ink.
INK_THRESHOLD = 240
# Breathing room left around the detected ink, as a fraction of the page. Without it a crop can
# shave the edge of a card that runs right up to the ink it was detected by.
PADDING = 0.01


def _ink_box(path: Path, page_number: int):
    """The fraction-of-page box (left, top, right, bottom) containing the page's ink.

    Returns `None` when the page is blank or cannot be rendered — the caller then uses the whole
    page, which is never wrong, only less tight.
    """
    from pdf2image import convert_from_path
    from PIL import ImageChops, ImageOps

    try:
        images = convert_from_path(
            str(path), dpi=DETECT_DPI, first_page=page_number + 1, last_page=page_number + 1
        )
    except Exception:
        return None
    if not images:
        return None

    grey = ImageOps.grayscale(images[0])
    # Everything at or above the threshold becomes white, so `getbbox` sees only the ink.
    mask = grey.point(lambda value: 0 if value >= INK_THRESHOLD else 255)
    box = ImageChops.difference(mask, ImageChops.constant(mask, 0)).getbbox()
    if box is None:
        return None

    width, height = grey.size
    left, top, right, bottom = box
    return (
        max(0.0, left / width - PADDING),
        max(0.0, top / height - PADDING),
        min(1.0, right / width + PADDING),
        min(1.0, bottom / height + PADDING),
    )


def _crop_to_ink(page, path: Path, page_number: int) -> None:
    """Narrow the page's crop box to its content, in place.

    Sets `cropbox` rather than rewriting the page: the drawing instructions are untouched, so the
    card stays vector and nothing is destroyed — only the visible window changes.
    """
    fractions = _ink_box(path, page_number)
    if fractions is None:
        return
    left_f, top_f, right_f, bottom_f = fractions
    box = page.mediabox
    x0, y0 = float(box.left), float(box.bottom)
    width, height = float(box.width), float(box.height)

    page.cropbox.left = x0 + left_f * width
    page.cropbox.right = x0 + right_f * width
    # Image rows run top-down while PDF y-coordinates run bottom-up, so the two flip.
    page.cropbox.top = y0 + (1 - top_f) * height
    page.cropbox.bottom = y0 + (1 - bottom_f) * height


def _place(sheet, source, index: int) -> None:
    """Stamp one cropped page into its cell, scaled to fit and centred."""
    cell_w = (SHEET[0] - 2 * MARGIN - (COLUMNS - 1) * GUTTER) / COLUMNS
    cell_h = (SHEET[1] - 2 * MARGIN - (ROWS - 1) * GUTTER) / ROWS
    column, row = index % COLUMNS, index // COLUMNS

    box = source.cropbox
    width, height = float(box.width), float(box.height)
    if width <= 0 or height <= 0:
        return
    # Fit, never fill: a card must not be cropped or stretched to square up a cell.
    scale = min(cell_w / width, cell_h / height)

    # The source draws in its own coordinates, so shift its crop origin to zero before placing it.
    x = MARGIN + column * (cell_w + GUTTER) + (cell_w - width * scale) / 2
    y = SHEET[1] - MARGIN - (row + 1) * cell_h - row * GUTTER + (cell_h - height * scale) / 2
    transformation = (
        Transformation()
        .translate(-float(box.left), -float(box.bottom))
        .scale(scale)
        .translate(x, y)
    )
    sheet.merge_transformed_page(source, transformation)


def card_sheets(documents: list) -> list:
    """Compose every page of `documents` into 2×2 sheets, in the order given.

    The order is the caller's: client card before spouse card, front before back, which is how the
    office reads them off the paper file.
    """
    root = Path(settings.DOCUMENTS_ROOT)
    pages = []
    for document in documents:
        path = root / document.file_path
        # Missing files are the compiled export's business to refuse loudly (§10.3) — it checks
        # every attachment itself, so skipping here cannot hide one.
        if not path.is_file():
            continue
        reader = PdfReader(str(path))
        for number, page in enumerate(reader.pages):
            _crop_to_ink(page, path, number)
            pages.append(page)

    sheets = []
    for start in range(0, len(pages), PER_SHEET):
        sheet = PageObject.create_blank_page(width=SHEET[0], height=SHEET[1])
        for index, source in enumerate(pages[start : start + PER_SHEET]):
            _place(sheet, source, index)
        sheets.append(sheet)
    return sheets


def sheets_as_pdf(documents: list) -> bytes:
    """The card sheets as a standalone PDF — the shape `merge_pdfs` already consumes."""
    writer = PdfWriter()
    for sheet in card_sheets(documents):
        writer.add_page(sheet)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()
