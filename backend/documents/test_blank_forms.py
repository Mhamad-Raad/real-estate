"""The blank forms the office prints from the Templates screen (§6.6, UC-039).

A `request_form` is the second kind of `DocumentTemplate`: no placeholders, stored as the PDF the
office supplied, printed as supplied and scanned back in as the optional `Request` document. The
whole point is that the sheet a citizen signs is **their file**, so the tests that matter here are
the ones pinning that nothing re-renders, re-encodes or fills it in.
"""

import tempfile
from pathlib import Path
from urllib.parse import quote

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.test import APITestCase

from accounts.models import User
from catalog import document_types

from .management.commands.install_templates import FILENAMES, TEMPLATES_DIR
from .models import DocumentTemplate
from .preview import render_template_preview
from .rendering import RenderError
from .services import create_template

BLANK_TYPE = DocumentTemplate.TemplateType.REQUEST_FORM
SHIPPED_FORM = TEMPLATES_DIR / FILENAMES[BLANK_TYPE]


def install_shipped_form(name: str = "request_form") -> DocumentTemplate:
    """Register the office's own file exactly as `install_templates` does."""
    content = SHIPPED_FORM.read_bytes()
    return create_template(
        template_type=BLANK_TYPE,
        name=name,
        upload=SimpleUploadedFile(SHIPPED_FORM.name, content),
        actor=None,
    )


@override_settings(LETTER_TEMPLATES_ROOT=Path(tempfile.mkdtemp()))
class BlankFormStorageTests(TestCase):
    def test_the_office_form_ships_in_the_repo_as_a_pdf(self):
        """It is installed from the codebase like every other template (§6.6, UC-010)."""
        self.assertTrue(SHIPPED_FORM.is_file(), f"{SHIPPED_FORM} is not in the repo")
        self.assertEqual(SHIPPED_FORM.suffix, ".pdf")

    def test_it_is_stored_as_a_pdf_not_under_a_docx_name(self):
        """`write_template` hard-coded `.docx`; a PDF filed under that name misdescribes itself."""
        template = install_shipped_form()

        self.assertTrue(template.file_path.endswith(".pdf"), template.file_path)
        self.assertTrue((settings.LETTER_TEMPLATES_ROOT / template.file_path).is_file())

    def test_the_stored_bytes_are_the_office_file_unchanged(self):
        """This sheet is signed by a citizen and filed — it must be their document, not a copy of
        it that went through an encoder."""
        template = install_shipped_form()

        stored = (settings.LETTER_TEMPLATES_ROOT / template.file_path).read_bytes()
        self.assertEqual(stored, SHIPPED_FORM.read_bytes())

    def test_a_corrupt_form_is_refused_at_install(self):
        """Same discipline as a letter: it fails here, not in front of the office."""
        with self.assertRaises(ValidationError):
            create_template(
                template_type=BLANK_TYPE,
                name="broken",
                upload=SimpleUploadedFile("broken.pdf", b"%PDF-1.7 truncated"),
                actor=None,
            )

    def test_a_letter_type_still_refuses_a_pdf(self):
        """The blank-form branch must not have opened the docx path to anything else."""
        with self.assertRaises(ValidationError):
            create_template(
                template_type=DocumentTemplate.TemplateType.ELIGIBILITY_SINGLE,
                name="wrong",
                upload=SimpleUploadedFile("f.pdf", SHIPPED_FORM.read_bytes()),
                actor=None,
            )


@override_settings(LETTER_TEMPLATES_ROOT=Path(tempfile.mkdtemp()))
class BlankFormPreviewTests(APITestCase):
    """The screen's preview IS the print path for a blank form, so it carries the real sheet."""

    def setUp(self):
        self.admin = User.objects.create_user("bf_adm", password="pw12345678", role=User.Role.ADMIN)
        self.template = install_shipped_form()

    def test_the_preview_serves_the_form_byte_for_byte(self):
        """Not a sample-data render — there is nothing to fill in, and a re-render would put a
        LibreOffice reflow of a scan on paper instead of the office's own page."""
        self.assertEqual(render_template_preview(self.template), SHIPPED_FORM.read_bytes())

    def test_the_endpoint_returns_the_form_under_its_sorani_name(self):
        """The office reads this name on paper; `request_form_preview.pdf` tells them nothing
        (§6.7, UC-060), and the browser would otherwise save it as the blob id (UC-058)."""
        self.client.force_authenticate(self.admin)

        resp = self.client.get(reverse("document-template-preview", args=[self.template.id]))

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(b"".join(resp.streaming_content), SHIPPED_FORM.read_bytes())
        # A Sorani name travels RFC 5987 percent-encoded; the client decodes it before saving.
        self.assertIn(
            quote(f"{document_types.name_ckb(document_types.REQUEST)}.pdf"),
            resp["Content-Disposition"],
        )

    def test_a_missing_file_is_a_404_not_a_500(self):
        (settings.LETTER_TEMPLATES_ROOT / self.template.file_path).unlink()
        self.client.force_authenticate(self.admin)

        resp = self.client.get(reverse("document-template-preview", args=[self.template.id]))

        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_generation_refuses_to_fill_a_blank_form_in(self):
        """The choke point every render passes through — docxtpl on a PDF would otherwise surface
        as an unreadable-zip error from inside the worker."""
        from .generation import render_to_pdf

        with self.assertRaises(RenderError):
            render_to_pdf(self.template, {}, Path(tempfile.gettempdir()))


@override_settings(LETTER_TEMPLATES_ROOT=Path(tempfile.mkdtemp()))
class BlankFormListingTests(APITestCase):
    def test_each_row_says_whether_it_is_a_blank_form(self):
        """It rides on the row because the row is what the screen holds. Read from the separate
        vocabulary endpoint instead, a slow or failed second request left the office's form worded
        AND operated as a letter — no Print button, which is the only reason the entry exists."""
        self.client.force_authenticate(
            User.objects.create_user("bf_voc", password="pw12345678", role=User.Role.ADMIN)
        )
        form = install_shipped_form()
        letter = DocumentTemplate.objects.create(
            template_type=DocumentTemplate.TemplateType.ELIGIBILITY_SINGLE,
            name="L",
            file_path="x/y.docx",
            sha256="0" * 64,
        )

        by_id = {row["id"]: row["is_blank_form"] for row in self.client.get("/api/v1/document-templates/").data}

        self.assertTrue(by_id[form.id])
        self.assertFalse(by_id[letter.id])
