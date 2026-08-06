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


def make_pdf(pages: int = 1) -> bytes:
    """A real, minimal PDF with the requested number of blank pages."""
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=595, height=842)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()
