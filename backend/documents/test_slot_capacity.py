"""A slot takes only what it declares (UC-085).

The office could keep adding to a full slot: a card that had already been scanned front and back
took a third and a fourth side after a re-scan, and the "2 of 2 sides" hint could only be capped
for display. `expected_parts` (§6.7) is now the capacity, enforced on **both** ways paper arrives —
the import button and a confirmed card scan, which files its document straight out of staging.
"""

import tempfile
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from catalog.document_types import CLIENT_ID
from clients.factories import make_client
from common.validators import SLOT_FILES_FULL, SLOT_SIDES_FULL
from processes.models import ProcessInstituteEntry
from processes.services import create_process

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
        self.assertEqual(self._post().status_code, status.HTTP_201_CREATED)
        self.assertEqual(self._post().status_code, status.HTTP_201_CREATED)

        resp = self._post()

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Document.objects.count(), 2)

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
