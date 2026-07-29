"""Test helpers for document content.

Uploads are validated by actually parsing the PDF, so a fixture like `b"%PDF-1.4 x"` no longer
passes. One place builds real bytes, so a stricter rule never has to be chased through the suite.
"""

from io import BytesIO

from pypdf import PdfWriter


def make_pdf(pages: int = 1) -> bytes:
    """A real, minimal PDF with the requested number of blank pages."""
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=595, height=842)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()
