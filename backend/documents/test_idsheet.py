"""Identity cards: four to a page in the compiled export (UC-081), and counted by side
rather than by file on the Step-1 slot (UC-083), because both sides live in one document."""

import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.test import TestCase, override_settings
from pypdf import PdfReader

from accounts.models import User
from catalog.document_types import CLIENT_ID, IDENTITY_TYPE_CODES, SPOUSE_ID
from clients.factories import make_client
from processes.services import create_process

from .compile import merge_pdfs
from .factories import HAS_POPPLER, NO_POPPLER_REASON, make_pdf, make_scan_pdf
from .idsheet import PER_SHEET, SHEET, _crop_to_ink, _ink_box, card_sheets
from .models import Document
from .services import create_document


@override_settings(DOCUMENTS_ROOT=Path(tempfile.mkdtemp()))
class IdSheetTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="ids", password="pw12345678", role=User.Role.ADMIN
        )
        self.process = create_process(
            client=make_client(full_name="B", pid="ID-1", mother_full_name="M"),
            assigned_lawyer=self.admin,
            actor=self.admin,
        )

    def _case(self, pid: str):
        """Another case to file a card on — a slot only takes two sides (UC-085), so a layout test
        that needs more card pages than that has to spread them over more than one beneficiary."""
        return create_process(
            client=make_client(full_name="B", pid=pid, mother_full_name="M"),
            assigned_lawyer=self.admin,
            actor=self.admin,
        )

    def _card(self, doc_type=CLIENT_ID, content=None, process=None) -> Document:
        return create_document(
            process=process or self.process,
            step_number=1,
            document_type=doc_type,
            input_source=Document.InputSource.IMPORTED,
            content=content if content is not None else make_pdf(),
            actor=self.admin,
        )

    def test_four_card_pages_become_one_sheet(self):
        """The reason this exists: both sides of two cards cost four near-empty pages.

        Filed as two documents of two pages since UC-103 — the second call to `_card` appends to
        the first and hands back the same, now two-page, document."""
        self._card()
        client = self._card()
        self._card(SPOUSE_ID)
        spouse = self._card(SPOUSE_ID)
        cards = [client, spouse]

        sheets = card_sheets(cards)

        self.assertEqual(len(sheets), 1)
        self.assertEqual(round(float(sheets[0].mediabox.width)), round(SHEET[0]))

    def test_more_cards_than_fit_flow_onto_another_sheet(self):
        """A sheet that is full must flow onto the next — none of the cards may be dropped."""
        cards = [self._card(process=self._case(f"MANY-{i}")) for i in range(PER_SHEET + 1)]

        self.assertEqual(len(card_sheets(cards)), 2)

    def test_a_two_page_card_file_lays_out_as_two_cells(self):
        """The scan path merges front and back into ONE file, so the sheet must count pages,
        not files — otherwise a scanned card takes a single cell and prints only its front."""
        both_sides = self._card(content=make_pdf(pages=2))

        sheets = card_sheets([both_sides, self._card(SPOUSE_ID, make_pdf(pages=2))])

        self.assertEqual(len(sheets), 1)  # 4 pages across 2 files still fits one sheet

    def test_a_card_whose_file_is_missing_is_skipped_not_crashed(self):
        """`merge_pdfs` refuses a missing attachment loudly; the sheet must not blow up first."""
        card = self._card()
        (Path(settings.DOCUMENTS_ROOT) / card.file_path).unlink()

        self.assertEqual(card_sheets([card]), [])

    def test_the_compiled_file_carries_the_sheet_instead_of_the_card_pages(self):
        # Four card pages the way the office actually files them: both sides in one scan each.
        self._card(content=make_pdf(pages=2))
        self._card(SPOUSE_ID, make_pdf(pages=2))
        other = create_document(
            process=self.process,
            step_number=2,
            document_type="InstituteDoc",
            input_source=Document.InputSource.IMPORTED,
            content=make_pdf(),
            actor=self.admin,
        )
        documents = list(Document.objects.filter(process=self.process).order_by("id"))

        merged = merge_pdfs(make_pdf(), documents)

        # cover + one card sheet + the institute document — not cover + 4 cards + 1.
        self.assertEqual(len(PdfReader(BytesIO(merged)).pages), 3)
        self.assertIsNotNone(other.id)

    def test_a_missing_attachment_still_fails_the_whole_export(self):
        """Composing the cards early must not let a fault in a later paper slip through (§10.3)."""
        card = self._card()
        broken = create_document(
            process=self.process,
            step_number=2,
            document_type="InstituteDoc",
            input_source=Document.InputSource.IMPORTED,
            content=make_pdf(),
            actor=self.admin,
        )
        (Path(settings.DOCUMENTS_ROOT) / broken.file_path).unlink()

        from .rendering import RenderError

        with self.assertRaises(RenderError):
            merge_pdfs(make_pdf(), [card, broken])


@override_settings(DOCUMENTS_ROOT=Path(tempfile.mkdtemp()))
class PageCountTests(TestCase):
    """A card is one document holding both sides, so the slot must count pages (UC-083)."""

    def setUp(self):
        self.admin = User.objects.create_user(
            username="pc", password="pw12345678", role=User.Role.ADMIN
        )
        self.process = create_process(
            client=make_client(full_name="B", pid="PC-1", mother_full_name="M"),
            assigned_lawyer=self.admin,
            actor=self.admin,
        )

    def _file(self, pages: int) -> Document:
        return create_document(
            process=self.process,
            step_number=1,
            document_type=CLIENT_ID,
            input_source=Document.InputSource.IMPORTED,
            content=make_pdf(pages=pages),
            actor=self.admin,
        )

    def test_a_card_scanned_as_one_two_page_file_counts_as_two_sides(self):
        """The reported bug: two scans merged into one document read "1 of 2 files"."""
        document = self._file(pages=2)

        self.assertEqual(document.page_count, 2)

    def test_one_side_on_its_own_counts_as_one(self):
        self.assertEqual(self._file(pages=1).page_count, 1)

    def test_two_separate_one_page_imports_become_one_two_page_card(self):
        """UC-103: importing the sides one at a time must reach the same place as scanning both
        at once — a single document of two pages, not two documents of one."""
        first = self._file(pages=1)
        second = self._file(pages=1)

        self.assertEqual(second.id, first.id)
        self.assertEqual(second.page_count, 2)

    def test_the_card_types_are_the_ones_that_count_pages(self):
        """The flag drives the label too, so the wrong one would say "sides" about paper files."""
        from catalog.document_types import DOCUMENT_TYPES

        by_page = {dt.code for dt in DOCUMENT_TYPES if dt.counts_pages}

        self.assertEqual(by_page, set(IDENTITY_TYPE_CODES))


@unittest.skipUnless(HAS_POPPLER, NO_POPPLER_REASON)
@override_settings(DOCUMENTS_ROOT=Path(tempfile.mkdtemp()))
class InkDetectionTests(TestCase):
    """Cropping to the ink is what makes four-to-a-page readable rather than smaller.

    The office scans a card onto a full page, so without this each card renders at roughly 44% of
    its real size in a quadrant; cropped, it comes out at full size or better.
    """

    def test_the_ink_box_finds_content_in_part_of_a_page(self):
        path = Path(settings.DOCUMENTS_ROOT) / "scan.pdf"
        path.write_bytes(make_scan_pdf(ink=(0.25, 0.10, 0.75, 0.30)))

        left, top, right, bottom = _ink_box(path, 0)

        # Detected to within the padding the crop deliberately leaves around the ink.
        self.assertAlmostEqual(left, 0.25, delta=0.03)
        self.assertAlmostEqual(top, 0.10, delta=0.03)
        self.assertAlmostEqual(right, 0.75, delta=0.03)
        self.assertAlmostEqual(bottom, 0.30, delta=0.03)

    def test_the_page_is_actually_cropped_to_its_ink_before_placing(self):
        """The link between finding the ink and using it.

        Without this the detector could be perfect and the crop never applied — which is exactly
        the difference between a card printing at 44% of its real size in a quadrant and at 103%.
        """
        path = Path(settings.DOCUMENTS_ROOT) / "card-on-a4.pdf"
        # A card occupying a fifth of a page: what the office's scanner produces.
        path.write_bytes(make_scan_pdf(ink=(0.28, 0.15, 0.72, 0.33)))
        page = PdfReader(str(path)).pages[0]
        full_width = float(page.mediabox.width)
        full_height = float(page.mediabox.height)

        _crop_to_ink(page, path, 0)

        self.assertAlmostEqual(float(page.cropbox.width) / full_width, 0.44, delta=0.05)
        self.assertAlmostEqual(float(page.cropbox.height) / full_height, 0.18, delta=0.05)

    def test_a_card_on_a_mostly_blank_page_is_not_shrunk_by_sharing_a_sheet(self):
        """End to end: four scans of this shape must still print the card at full size or better,
        which is the whole justification for putting four to a page (UC-081)."""
        from .idsheet import COLUMNS, GUTTER, MARGIN, ROWS

        path = Path(settings.DOCUMENTS_ROOT) / "card2.pdf"
        path.write_bytes(make_scan_pdf(ink=(0.28, 0.15, 0.72, 0.33)))
        page = PdfReader(str(path)).pages[0]
        _crop_to_ink(page, path, 0)

        cell_w = (SHEET[0] - 2 * MARGIN - (COLUMNS - 1) * GUTTER) / COLUMNS
        cell_h = (SHEET[1] - 2 * MARGIN - (ROWS - 1) * GUTTER) / ROWS
        scale = min(
            cell_w / float(page.cropbox.width), cell_h / float(page.cropbox.height)
        )

        self.assertGreater(scale, 0.95, "the card would print smaller than life on the sheet")

    def test_a_blank_page_reports_no_ink_and_is_left_whole(self):
        """No content to crop to is not a failure — the whole page is used, as before."""
        path = Path(settings.DOCUMENTS_ROOT) / "blank.pdf"
        path.write_bytes(make_pdf())

        self.assertIsNone(_ink_box(path, 0))

    def test_an_unreadable_file_reports_no_ink_rather_than_raising(self):
        """Cropping is an improvement, not a requirement — it must never fail an export."""
        path = Path(settings.DOCUMENTS_ROOT) / "broken.pdf"
        path.write_bytes(b"%PDF-1.4 not really a pdf")

        self.assertIsNone(_ink_box(path, 0))
