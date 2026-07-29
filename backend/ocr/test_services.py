"""OCR run lifecycle, verification, and RBAC (§6.5, §7, §11)."""

from datetime import date
from unittest import mock

from django.conf import settings
from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.models import User
from clients.factories import make_client
from clients.models import Client
from common.models import ActivityLog
from documents.factories import make_pdf
from documents.models import Document
from documents.services import create_document
from processes.services import create_process

from .models import OcrRun
from .services import execute_ocr, verify_ocr

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

    def test_a_card_number_another_client_holds_is_refused_not_a_server_error(self):
        """A misread digit lands on the "no land twice" key (§3.7). The unique index would raise
        an IntegrityError — a 500 that tells the lawyer nothing — so it is caught first."""
        from rest_framework.exceptions import ValidationError

        make_client(full_name="Someone Else", pid="200103487811", mother_full_name="M")
        run = self._run()
        with self.assertRaises(ValidationError) as caught:
            verify_ocr(run=run, values={"pid": "200103487811"}, actor=self.lawyer)

        self.assertIn("Someone Else", str(caught.exception.detail["pid"]))
        self.client_row.refresh_from_db()
        self.assertEqual(self.client_row.pid, "OLD-1")

    def test_the_same_card_number_on_the_same_client_is_not_a_conflict(self):
        self.client_row.pid = "200103487811"
        self.client_row.save(update_fields=["pid"])
        run = self._run()
        verify_ocr(
            run=run, values={"pid": "200103487811", "full_name": "New"}, actor=self.lawyer
        )
        self.client_row.refresh_from_db()
        self.assertEqual(self.client_row.full_name, "New")

    def test_a_stale_client_version_is_rejected(self):
        """The verify screen writes the same columns as the client details panel (§4.1)."""
        from common.locking import StaleVersion

        run = self._run()
        with self.assertRaises(StaleVersion):
            verify_ocr(
                run=run,
                values={"full_name": "X"},
                actor=self.lawyer,
                client_version=self.client_row.version + 5,
            )

    def test_only_the_confirmed_columns_are_written(self):
        """A full save() would write back every column, including stale copies of fields the
        verify screen never loaded — silently undoing a concurrent edit on the same record."""
        run = self._run()
        written = {}
        original = Client.save

        def spy(instance, *args, **kwargs):
            written.update(kwargs)
            return original(instance, *args, **kwargs)

        with mock.patch.object(Client, "save", spy):
            verify_ocr(run=run, values={"mother_full_name": "New Mother"}, actor=self.lawyer)

        self.assertEqual(
            set(written["update_fields"]), {"mother_full_name", "version", "updated_at"}
        )
        self.client_row.refresh_from_db()
        self.assertEqual(self.client_row.mother_full_name, "New Mother")

    def test_the_api_requires_the_client_version(self):
        run = self._run()
        self.client.force_authenticate(self.lawyer)
        response = self.client.post(
            reverse("ocr-run-verify", args=[run.id]), {"full_name": "X"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("client_version", response.data)

    def test_a_verify_through_the_api_writes_the_client(self):
        run = self._run()
        self.client.force_authenticate(self.lawyer)
        response = self.client.post(
            reverse("ocr-run-verify", args=[run.id]),
            {"full_name": "Through The API", "client_version": self.client_row.version},
        )
        self.assertEqual(response.status_code, 200)
        self.client_row.refresh_from_db()
        self.assertEqual(self.client_row.full_name, "Through The API")


class ExecuteOcrTests(OcrTestBase):
    def test_a_failed_read_is_recorded_as_failed_not_as_an_empty_draft(self):
        """The whole point of the status column: a failure keeps its reason and the UI falls back
        to manual entry, instead of showing a confident-looking empty form."""
        run = self._run(status=OcrRun.Status.PENDING, draft={})
        with mock.patch(
            "ocr.reader.read_document", side_effect=OSError("cannot read the file")
        ):
            with self.assertRaises(OSError):
                execute_ocr(run.id)

        run.refresh_from_db()
        self.document.refresh_from_db()
        self.assertEqual(run.status, OcrRun.Status.FAILED)
        self.assertIn("cannot read the file", run.error)
        self.assertEqual(run.draft, {})
        self.assertEqual(self.document.ocr_status, Document.OcrStatus.FAILED)

    def test_the_stored_failure_reason_does_not_leak_the_store_path(self):
        """`error` is served straight to the browser."""
        path = f"{settings.DOCUMENTS_ROOT}/A_General/x.pdf"
        run = self._run(status=OcrRun.Status.PENDING, draft={})
        with mock.patch("ocr.reader.read_document", side_effect=OSError(f"missing {path}")):
            with self.assertRaises(OSError):
                execute_ocr(run.id)

        run.refresh_from_db()
        self.assertNotIn(str(settings.DOCUMENTS_ROOT), run.error)
        self.assertIn("<documents>", run.error)

    def test_a_successful_read_stores_the_draft_and_awaits_a_human(self):
        run = self._run(status=OcrRun.Status.PENDING, draft={})
        with mock.patch("ocr.reader.read_document") as read:
            read.return_value.as_dict.return_value = DRAFT
            execute_ocr(run.id)

        run.refresh_from_db()
        self.document.refresh_from_db()
        self.assertEqual(run.status, OcrRun.Status.DONE)
        self.assertEqual(run.draft, DRAFT)
        self.assertEqual(self.document.ocr_status, Document.OcrStatus.DONE)
        # "done" means the engine finished, not that the data is trusted (§6.5).
        self.assertEqual(
            self.document.verification_status, Document.VerificationStatus.PENDING
        )
