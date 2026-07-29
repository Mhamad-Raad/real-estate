"""OCR run lifecycle, verification, and RBAC (§6.5, §7, §11)."""

from datetime import date

from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.models import User
from clients.factories import make_client
from common.models import ActivityLog
from documents.factories import make_pdf
from documents.models import Document
from documents.services import create_document
from processes.services import create_process

from .models import OcrRun
from .services import verify_ocr

DRAFT = {
    "fields": {
        "pid": {"value": "200103487811", "confidence": 96, "source": "mrz+front", "verified": True},
        "full_name": {"value": "محمد رعد", "confidence": 59, "source": "front", "verified": False},
        "mother_full_name": {
            "value": "دلسوز على", "confidence": 59, "source": "front", "verified": False
        },
        "date_of_birth": {
            "value": "2001-08-12", "confidence": 95, "source": "mrz", "verified": True
        },
    },
    "warnings": [],
}


class OcrTestBase(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="adm", password="pw12345678", role=User.Role.ADMIN
        )
        self.lawyer = User.objects.create_user(username="lw", password="pw12345678")
        self.other = User.objects.create_user(username="other", password="pw12345678")
        self.client_row = make_client(full_name="Old Name", pid="OLD-1", mother_full_name="Old M")
        self.process = create_process(
            client=self.client_row, assigned_lawyer=self.lawyer, actor=self.admin
        )
        self.document = create_document(
            process=self.process,
            step_number=1,
            document_type="ClientID",
            input_source=Document.InputSource.IMPORTED,
            content=make_pdf(),
            actor=self.lawyer,
        )

    def _run(self, **kwargs):
        return OcrRun.objects.create(
            document=kwargs.pop("document", self.document),
            requested_by=self.lawyer,
            status=kwargs.pop("status", OcrRun.Status.DONE),
            draft=kwargs.pop("draft", DRAFT),
            **kwargs,
        )


class StartOcrTests(OcrTestBase):
    def test_only_identity_documents_can_be_read(self):
        other = create_document(
            process=self.process,
            step_number=2,
            document_type="InstituteDoc",
            input_source=Document.InputSource.IMPORTED,
            content=make_pdf(),
            actor=self.lawyer,
        )
        self.client.force_authenticate(self.lawyer)
        response = self.client.post(reverse("ocr-run-list"), {"document": other.id})
        self.assertEqual(response.status_code, 400)

    def test_a_lawyer_who_is_not_the_assignee_is_refused(self):
        self.client.force_authenticate(self.other)
        response = self.client.post(reverse("ocr-run-list"), {"document": self.document.id})
        self.assertEqual(response.status_code, 403)

    def test_starting_is_audited_and_marks_the_document_pending(self):
        self.client.force_authenticate(self.lawyer)
        response = self.client.post(reverse("ocr-run-list"), {"document": self.document.id})

        self.assertEqual(response.status_code, 202)
        self.document.refresh_from_db()
        self.assertEqual(self.document.ocr_status, Document.OcrStatus.PENDING)
        self.assertTrue(
            ActivityLog.objects.filter(
                entity_type="OcrRun", entity_id=str(response.data["id"])
            ).exists()
        )


class VerifyTests(OcrTestBase):
    def test_accepted_values_are_written_to_the_client(self):
        run = self._run()
        verify_ocr(
            run=run,
            values={
                "pid": "200103487811",
                "full_name": "محمد رعد",
                "mother_full_name": "دلسوز على",
                "date_of_birth": date(2001, 8, 12),
            },
            actor=self.lawyer,
        )
        self.client_row.refresh_from_db()
        self.assertEqual(self.client_row.pid, "200103487811")
        self.assertEqual(self.client_row.mother_full_name, "دلسوز على")
        self.assertEqual(self.client_row.date_of_birth, date(2001, 8, 12))

    def test_the_humans_correction_wins_over_the_engines_reading(self):
        """What the person confirmed is what counts — OCR only proposed it."""
        run = self._run()
        verify_ocr(run=run, values={"full_name": "محمد رعد رضا"}, actor=self.lawyer)

        self.client_row.refresh_from_db()
        self.assertEqual(self.client_row.full_name, "محمد رعد رضا")

    def test_a_correction_is_recorded_so_ocr_quality_can_be_judged(self):
        run = self._run()
        verify_ocr(run=run, values={"full_name": "Corrected Name"}, actor=self.lawyer)

        entry = ActivityLog.objects.filter(
            action=ActivityLog.Action.VERIFY, entity_type="Client"
        ).latest("created_at")
        self.assertIn("full_name", entry.after["corrected"])
        self.assertEqual(entry.before["full_name"], "Old Name")

    def test_verification_does_not_lock_the_fields(self):
        """Verifying records that a human checked it; the data stays editable afterwards."""
        run = self._run()
        verify_ocr(run=run, values={"full_name": "First Value"}, actor=self.lawyer)

        self.client_row.refresh_from_db()
        self.client_row.full_name = "Changed Later"
        self.client_row.save(update_fields=["full_name"])

        self.client_row.refresh_from_db()
        self.assertEqual(self.client_row.full_name, "Changed Later")

    def test_marks_the_document_verified(self):
        run = self._run()
        verify_ocr(run=run, values={"full_name": "X"}, actor=self.lawyer)

        self.document.refresh_from_db()
        self.assertEqual(
            self.document.verification_status, Document.VerificationStatus.VERIFIED
        )

    def test_an_unfinished_run_cannot_be_verified(self):
        from rest_framework.exceptions import ValidationError

        run = self._run(status=OcrRun.Status.RUNNING, draft={})
        with self.assertRaises(ValidationError):
            verify_ocr(run=run, values={"full_name": "X"}, actor=self.lawyer)

    def test_a_run_cannot_be_verified_twice(self):
        from rest_framework.exceptions import ValidationError

        run = self._run()
        verify_ocr(run=run, values={"full_name": "X"}, actor=self.lawyer)
        with self.assertRaises(ValidationError):
            verify_ocr(run=run, values={"full_name": "Y"}, actor=self.lawyer)

    def test_blank_values_are_skipped_rather_than_wiping_the_record(self):
        run = self._run()
        verify_ocr(run=run, values={"full_name": "", "pid": "200103487811"}, actor=self.lawyer)

        self.client_row.refresh_from_db()
        self.assertEqual(self.client_row.full_name, "Old Name")
        self.assertEqual(self.client_row.pid, "200103487811")

    def test_a_spouse_card_fills_the_spouse_columns(self):
        spouse_doc = create_document(
            process=self.process,
            step_number=1,
            document_type="SpouseID",
            input_source=Document.InputSource.IMPORTED,
            content=make_pdf(),
            actor=self.lawyer,
        )
        run = self._run(document=spouse_doc)
        verify_ocr(
            run=run,
            values={
                "full_name": "Spouse Name",
                "mother_full_name": "Spouse Mother",
                "date_of_birth": date(1995, 3, 4),
            },
            actor=self.lawyer,
        )
        self.client_row.refresh_from_db()
        self.assertEqual(self.client_row.spouse_name, "Spouse Name")
        self.assertEqual(self.client_row.spouse_mother_full_name, "Spouse Mother")
        self.assertEqual(self.client_row.spouse_date_of_birth, date(1995, 3, 4))
        # A spouse's own PID is not stored — the client's is the identity key (§3.7).
        self.assertEqual(self.client_row.pid, "OLD-1")

    def test_a_non_assignee_cannot_verify(self):
        run = self._run()
        self.client.force_authenticate(self.other)
        response = self.client.post(
            reverse("ocr-run-verify", args=[run.id]), {"full_name": "X"}
        )
        self.assertEqual(response.status_code, 403)
