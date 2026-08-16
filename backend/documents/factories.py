"""Test helpers for document content.

Uploads are validated by actually parsing the PDF, so a fixture like `b"%PDF-1.4 x"` no longer
passes. One place builds real bytes, so a stricter rule never has to be chased through the suite.
"""

import shutil
from io import BytesIO

from django.conf import settings
from pypdf import PdfWriter

# Anything that renders a `.docx` needs the real binary, which the macOS native-dev path does not
# have (§running.md). Declared once here rather than re-derived per test module: it was already
# defined twice, and the module that forgot it left the suite **red** on the documented native
# path instead of skipping like its siblings (It.8).
HAS_LIBREOFFICE = shutil.which(settings.LIBREOFFICE_BIN) is not None
NO_LIBREOFFICE_REASON = "LibreOffice not installed (run inside the container)"

# Poppler renders a page so the ID sheet can find its ink (§10.3, UC-081). Same guard shape as
# LibreOffice above: present in the image, optional on a native macOS dev box.
HAS_POPPLER = shutil.which("pdftoppm") is not None
NO_POPPLER_REASON = "Poppler not installed (run inside the container)"


def make_scan_pdf(*, page=(595, 842), ink=(0.3, 0.2, 0.7, 0.4)) -> bytes:
    """A page shaped like a real office scan: ink over part of it, blank elsewhere.

    `make_pdf` produces genuinely blank pages, which cannot exercise anything that looks at what
    a page contains — the ID sheet crops to the ink, so it needs a page that has some.
    `ink` is (left, top, right, bottom) as fractions of the page.
    """
    from io import BytesIO

    from PIL import Image, ImageDraw

    scale = 2  # pixels per point; enough for a 50-dpi detection pass to see the edges cleanly
    width, height = int(page[0] * scale), int(page[1] * scale)
    image = Image.new("RGB", (width, height), "white")
    ImageDraw.Draw(image).rectangle(
        [ink[0] * width, ink[1] * height, ink[2] * width, ink[3] * height], fill="black"
    )
    buffer = BytesIO()
    # `resolution` is what makes the saved page come out at the requested point size.
    image.save(buffer, "PDF", resolution=72 * scale)
    return buffer.getvalue()


def make_pdf(pages: int = 1) -> bytes:
    """A real, minimal PDF with the requested number of blank pages."""
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=595, height=842)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()
