"""A slot takes only what it declares (UC-085).

The office could keep adding to a full slot: a card that had already been scanned front and back
took a third and a fourth side after a re-scan, and the "2 of 2 sides" hint could only be capped
for display. `expected_parts` (§6.7) is now the capacity, enforced on **both** ways paper arrives —
the import button and a confirmed card scan, which files its document straight out of staging.
"""

import tempfile
from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from catalog.document_types import CLIENT_ID, SPOUSE_ID
from clients.factories import make_client
from common.validators import SLOT_FILES_FULL, SLOT_SIDES_FULL
from processes.models import ProcessInstituteEntry
from processes.services import create_process

from . import filestore
from .factories import make_pdf
from .models import Document


@override_settings(DOCUMENTS_ROOT=Path(tempfile.mkdtemp()))
class SlotCapacityTests(APITestCase):
    def setUp(self):
        self.lawyer = User.objects.create_user("cap", password="pw12345678")
        self.process = create_process(
            client=make_client(full_name="B", pid="CAP-1", mother_full_name="M"),
            assigned_lawyer=self.lawyer,
            actor=self.lawyer,
        )
        self.client.force_authenticate(self.lawyer)

    def _post(self, *, document_type=CLIENT_ID, step=1, pages=1, entry=None):
        body = {
            "process": self.process.id,
            "step_number": step,
            "document_type": document_type,
            "file": SimpleUploadedFile(
                "p.pdf", make_pdf(pages=pages), content_type="application/pdf"
            ),
        }
        if entry is not None:
            body["institute_entry"] = entry.id
        return self.client.post(reverse("document-list"), body, format="multipart")

    def test_a_card_takes_two_sides_and_refuses_a_third(self):
        """UC-103: the second side **joins** the first, so two sides are one two-page document —
        and the third is still refused, because capacity counts sides, not rows."""
        self.assertEqual(self._post().status_code, status.HTTP_201_CREATED)
        self.assertEqual(self._post().status_code, status.HTTP_201_CREATED)

        resp = self._post()

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Document.objects.count(), 1)
        self.assertEqual(Document.objects.get().page_count, 2)

    def test_the_second_side_joins_the_first_instead_of_filing_beside_it(self):
        """UC-103, the office's ask: a card is one paper with two sides, so the archive and the
        screen should show one entry holding page 1 and page 2 — not two loose files to pair up."""
        first = self._post()
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        document_id = Document.objects.get().id
        before = Document.objects.get().sha256

        self.assertEqual(self._post().status_code, status.HTTP_201_CREATED)

        document = Document.objects.get()
        self.assertEqual(document.id, document_id, "a second row was filed for one card")
        self.assertEqual(document.page_count, 2)
        self.assertNotEqual(document.sha256, before, "the merged file was not re-hashed")
        # The bytes on disk must agree with the row that describes them.
        stored = (settings.DOCUMENTS_ROOT / document.file_path).read_bytes()
        self.assertEqual(filestore.count_pages(stored), 2)
        self.assertEqual(document.size_bytes, len(stored))

    def test_a_scanned_side_joins_the_card_an_import_started(self):
        """UC-103 covers **both** filing paths — the office scans some sides and imports others,
        and a card must end as one document however its sides arrived. The scan path files from
        staging and never touched `create_document`, so it needed the rule of its own."""
        from documents.services import file_staged_document

        self._post()
        document_id = Document.objects.get().id
        folder = (settings.DOCUMENTS_ROOT / Document.objects.get().file_path).parent
        # Counted as a delta: the class shares one document root, so earlier tests have already
        # left files in this folder.
        before = set(folder.glob("*.pdf"))
        staged = filestore.staging_path("probe")
        filestore.write_pdf(staged, make_pdf(pages=1))

        document = file_staged_document(
            staged_path=str(staged),
            process=self.process,
            step_number=1,
            document_type=CLIENT_ID,
            actor=self.lawyer,
            sha256="0" * 64,
            size_bytes=1,
        )

        self.assertEqual(Document.objects.count(), 1)
        self.assertEqual(document.id, document_id)
        self.assertEqual(document.page_count, 2)
        # No name was claimed for a side that never became a document of its own (UC-097).
        self.assertEqual(set(folder.glob("*.pdf")) - before, set())

    def test_the_spouse_card_merges_on_its_own_slot(self):
        """The two cards are separate slots — a spouse's side must never join the beneficiary's."""
        self._post()
        self._post(document_type=SPOUSE_ID)
        self._post(document_type=SPOUSE_ID)

        self.assertEqual(Document.objects.count(), 2)
        self.assertEqual(
            {(d.document_type, d.page_count) for d in Document.objects.all()},
            {(CLIENT_ID, 1), (SPOUSE_ID, 2)},
        )

    def test_a_card_already_holding_both_sides_in_one_file_is_full(self):
        """The scan path merges front and back into ONE document — counting rows would call that
        card half-filed and let a re-scan add two more sides on top of it."""
        self._post(pages=2)

        resp = self._post()

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_a_three_page_scan_does_not_fit_a_card_slot_at_all(self):
        resp = self._post(pages=3)

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Document.objects.exists())

    def test_a_single_paper_slot_takes_one_however_many_pages_it_has(self):
        """Only a card counts pages: a three-page agreement is one paper, and the second is not."""
        first = self._post(document_type="SignedAgreement", pages=3)

        second = self._post(document_type="SignedAgreement")

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)

    def test_the_real_estate_slot_takes_the_two_papers_the_office_files(self):
        for _ in range(2):
            self.assertEqual(
                self._post(document_type="RealEstate", step=4).status_code,
                status.HTTP_201_CREATED,
            )

        self.assertEqual(
            self._post(document_type="RealEstate", step=4).status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_the_real_estate_slot_also_takes_the_pair_as_one_two_page_file(self):
        """UC-109: the office files these either as two one-page scans or as one two-page PDF.
        Counting rows called the merged shape half-done and left room for two more papers."""
        first = self._post(document_type="RealEstate", step=4, pages=2)

        second = self._post(document_type="RealEstate", step=4)

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)

    def test_the_two_municipality_papers_stay_two_documents(self):
        """Unlike a card, they are two different papers — the slot counts their pages together
        but must not merge them into one file."""
        for _ in range(2):
            self._post(document_type="RealEstate", step=4)

        self.assertEqual(Document.objects.filter(document_type="RealEstate").count(), 2)

    def test_deleting_a_document_makes_room_again(self):
        """Replacing a scan is delete-then-upload — the rule counts live rows, so it works."""
        doc_id = self._post(pages=2).data["id"]
        self.client.delete(reverse("document-detail", args=[doc_id]))

        self.assertEqual(self._post(pages=2).status_code, status.HTTP_201_CREATED)

    def test_the_refusal_is_a_translated_key_not_an_english_sentence(self):
        """Every message the office reads is localized (§9) — see `common.test_validation_keys`."""
        self._post(pages=2)

        resp = self._post()

        self.assertEqual(resp.data["file"][0], SLOT_SIDES_FULL)
        self.assertEqual(
            self._post(document_type="Request").status_code, status.HTTP_201_CREATED
        )

    def test_each_institute_gets_its_own_acceptance(self):
        """Steps 2-4 file the same generic `InstituteDoc` once per institute, so the capacity is
        per entry — counting them across the process would call the second institute's slot full."""
        entries = [
            ProcessInstituteEntry.objects.create(
                process=self.process, step_number=2, institute_code=code
            )
            for code in ("A", "B")
        ]

        for entry in entries:
            resp = self._post(document_type="InstituteDoc", step=2, entry=entry)
            self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        refused = self._post(document_type="InstituteDoc", step=2, entry=entries[0])

        self.assertEqual(refused.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(refused.data["file"][0], SLOT_FILES_FULL)
