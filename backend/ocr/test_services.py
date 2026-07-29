"""Card-scan staging, reading and confirmation (§6.5, §6.7, §7, §11)."""

import tempfile
from datetime import date, timedelta
from io import BytesIO, StringIO
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APITestCase

from accounts.models import User
from clients.factories import make_client
from clients.models import Client
from common.locking import StaleVersion
from common.models import ActivityLog
from documents.factories import make_pdf
from documents.models import Document
from processes.models import Process
from processes.services import create_process

from . import sweep
from .models import CardScan
from .services import confirm_scan, read_scan, stage_scan

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

CONFIRMED = {
    "pid": "200103487811",
    "full_name": "محمد رعد",
    "mother_full_name": "دلسوز على",
    "date_of_birth": date(2001, 8, 12),
}


# These tests write real files; keep them out of the office's document store.
@override_settings(DOCUMENTS_ROOT=Path(tempfile.mkdtemp()))
class ScanTestBase(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="adm", password="pw12345678", role=User.Role.ADMIN
        )
        self.lawyer = User.objects.create_user(username="lw", password="pw12345678")
        self.other = User.objects.create_user(username="other", password="pw12345678")

    def _scan(self, **kwargs):
        """A staged scan with its file actually on disk, as staging leaves it."""
        return stage_scan(
            content=kwargs.pop("content", make_pdf()),
            document_type=kwargs.pop("document_type", "ClientID"),
            actor=kwargs.pop("actor", self.lawyer),
            **kwargs,
        )

    def _read(self, scan, draft=DRAFT):
        scan.status = CardScan.Status.DONE
        scan.draft = draft
        scan.save(update_fields=["status", "draft"])
        return scan


class StagingTests(ScanTestBase):
    def test_a_card_is_written_to_disk_before_anything_else(self):
        """A photograph that exists only in a browser tab is one closed window from being lost."""
        scan = self._scan()
        self.assertTrue((settings.DOCUMENTS_ROOT / scan.file_path).exists())
        self.assertIn("_staging", scan.file_path)
        self.assertEqual(scan.status, CardScan.Status.PENDING)

    def test_staging_needs_no_client_or_case(self):
        """The whole point: the card is what creates the person."""
        self._scan()
        self.assertFalse(Client.objects.exists())
        self.assertFalse(Process.objects.exists())

    def test_a_photographed_card_is_converted_to_pdf_on_arrival(self):
        from io import BytesIO

        from PIL import Image
        from documents import filestore

        buffer = BytesIO()
        Image.new("RGB", (60, 40), (255, 0, 0)).save(buffer, format="JPEG")
        scan = self._scan(content=buffer.getvalue())

        stored = (settings.DOCUMENTS_ROOT / scan.file_path).read_bytes()
        self.assertTrue(filestore.is_readable_pdf(stored))

    def test_both_sides_become_one_two_page_pdf(self):
        """A card is one document with two sides — one row, one file, and the reader sees both
        sides together, which is what makes the front↔MRZ cross-check possible."""
        from pypdf import PdfReader

        scan = self._scan(content=make_pdf(), back=make_pdf())
        stored = (settings.DOCUMENTS_ROOT / scan.file_path).read_bytes()

        self.assertEqual(len(PdfReader(BytesIO(stored)).pages), 2)
        self.assertEqual(CardScan.objects.count(), 1)

    def test_two_photographs_merge_into_one_pdf(self):
        from PIL import Image
        from pypdf import PdfReader

        def jpeg(colour):
            buffer = BytesIO()
            Image.new("RGB", (60, 40), colour).save(buffer, format="JPEG")
            return buffer.getvalue()

        scan = self._scan(content=jpeg((255, 0, 0)), back=jpeg((0, 0, 255)))
        stored = (settings.DOCUMENTS_ROOT / scan.file_path).read_bytes()
        self.assertEqual(len(PdfReader(BytesIO(stored)).pages), 2)

    def test_the_back_is_optional(self):
        from pypdf import PdfReader

        scan = self._scan(content=make_pdf())
        stored = (settings.DOCUMENTS_ROOT / scan.file_path).read_bytes()
        self.assertEqual(len(PdfReader(BytesIO(stored)).pages), 1)

    def test_a_malformed_back_is_refused(self):
        with self.assertRaises(ValidationError) as caught:
            self._scan(content=make_pdf(), back=b"\xff\xd8\xff" + b"garbage" * 50)
        self.assertIn("back", caught.exception.detail)

    def test_only_identity_cards_can_be_staged(self):
        with self.assertRaises(ValidationError):
            self._scan(document_type="RealEstate")

    def test_a_malformed_image_is_refused(self):
        with self.assertRaises(ValidationError):
            self._scan(content=b"\xff\xd8\xff" + b"garbage" * 50)

    def test_staging_is_audited(self):
        scan = self._scan()
        self.assertTrue(
            ActivityLog.objects.filter(entity_type="CardScan", entity_id=str(scan.id)).exists()
        )


class ReadingTests(ScanTestBase):
    def test_a_failed_read_is_recorded_as_failed_not_as_an_empty_draft(self):
        """The status column exists so the UI can fall back to manual entry, instead of showing a
        confident-looking empty form."""
        scan = self._scan()
        with mock.patch("ocr.reader.read_card", side_effect=OSError("cannot read the file")):
            with self.assertRaises(OSError):
                read_scan(scan.id)

        scan.refresh_from_db()
        self.assertEqual(scan.status, CardScan.Status.FAILED)
        self.assertIn("cannot read the file", scan.error)
        self.assertEqual(scan.draft, {})
        # The scan itself survives — the lawyer keeps it and types the values by hand.
        self.assertTrue((settings.DOCUMENTS_ROOT / scan.file_path).exists())

    def test_the_stored_failure_reason_does_not_leak_the_store_path(self):
        """`error` is served straight to the browser."""
        scan = self._scan()
        path = f"{settings.DOCUMENTS_ROOT}/_staging/x.pdf"
        with mock.patch("ocr.reader.read_card", side_effect=OSError(f"missing {path}")):
            with self.assertRaises(OSError):
                read_scan(scan.id)

        scan.refresh_from_db()
        self.assertNotIn(str(settings.DOCUMENTS_ROOT), scan.error)
        self.assertIn("<documents>", scan.error)

    def test_a_re_read_replaces_the_draft_rather_than_keeping_a_history(self):
        scan = self._scan()
        with mock.patch("ocr.reader.read_card") as read:
            read.return_value.as_dict.return_value = {"fields": {}, "warnings": ["first"]}
            read_scan(scan.id)
            read.return_value.as_dict.return_value = DRAFT
            read_scan(scan.id)

        scan.refresh_from_db()
        self.assertEqual(scan.draft, DRAFT)
        self.assertEqual(CardScan.objects.count(), 1)


class ConfirmCreatesTheClientTests(ScanTestBase):
    def test_confirming_creates_the_client_the_case_and_the_filed_document(self):
        scan = self._read(self._scan())
        confirm_scan(
            scan=scan, values=dict(CONFIRMED), actor=self.lawyer, assigned_lawyer=self.lawyer
        )

        client = Client.objects.get()
        self.assertEqual(client.pid, "200103487811")
        self.assertEqual(client.full_name, "محمد رعد")
        self.assertEqual(client.date_of_birth, date(2001, 8, 12))

        document = Document.objects.get()
        self.assertEqual(document.process.client, client)
        self.assertEqual(document.step_number, 1)
        self.assertEqual(document.verification_status, Document.VerificationStatus.VERIFIED)
        self.assertEqual(document.input_source, Document.InputSource.SCANNED)

    def test_the_file_lands_in_the_persons_folder_under_its_composed_name(self):
        """The folder is keyed by the PID and the name by the person — both of which the card is
        what supplies, so filing can only happen once the reading is confirmed (§6.7)."""
        scan = self._read(self._scan())
        staged = scan.file_path
        confirm_scan(
            scan=scan, values=dict(CONFIRMED), actor=self.lawyer, assigned_lawyer=self.lawyer
        )

        document = Document.objects.get()
        client = Client.objects.get()
        self.assertIn(f"{client.id:06d}_200103487811", document.file_path)
        self.assertIn("ClientID", document.display_filename)
        self.assertTrue((settings.DOCUMENTS_ROOT / document.file_path).exists())
        # Nothing left behind in staging.
        self.assertFalse((settings.DOCUMENTS_ROOT / staged).exists())
        scan.refresh_from_db()
        self.assertEqual(scan.file_path, "")

    def test_the_moved_file_is_the_same_bytes(self):
        content = make_pdf(2)
        scan = self._read(self._scan(content=content))
        confirm_scan(
            scan=scan, values=dict(CONFIRMED), actor=self.lawyer, assigned_lawyer=self.lawyer
        )
        document = Document.objects.get()
        self.assertEqual((settings.DOCUMENTS_ROOT / document.file_path).read_bytes(), content)
        self.assertEqual(document.sha256, scan.sha256)

    def test_a_correction_is_recorded_so_ocr_quality_can_be_judged(self):
        scan = self._read(self._scan())
        confirm_scan(
            scan=scan,
            values={**CONFIRMED, "full_name": "محمد رعد رضا"},
            actor=self.lawyer,
            assigned_lawyer=self.lawyer,
        )
        entry = ActivityLog.objects.filter(
            action=ActivityLog.Action.VERIFY, entity_type="Client"
        ).latest("created_at")
        self.assertIn("full_name", entry.after["corrected"])
        self.assertNotIn("pid", entry.after["corrected"])

    def test_a_failed_reading_can_still_be_confirmed_by_hand(self):
        """OCR is an assist, never a gate — manual entry always works (§6.5)."""
        scan = self._scan()
        scan.status = CardScan.Status.FAILED
        scan.error = "unreadable"
        scan.save(update_fields=["status", "error"])

        confirm_scan(
            scan=scan,
            values={**CONFIRMED, "full_name": "Typed By Hand"},
            actor=self.lawyer,
            assigned_lawyer=self.lawyer,
        )
        self.assertEqual(Client.objects.get().full_name, "Typed By Hand")
        self.assertTrue(Document.objects.exists())

    def test_a_card_number_another_client_holds_is_refused_not_a_server_error(self):
        """A misread digit lands on the "no land twice" key (§3.7). The unique index would raise
        an IntegrityError — a 500 that tells the lawyer nothing — so it is caught first."""
        make_client(full_name="Someone Else", pid="200103487811", mother_full_name="M")
        scan = self._read(self._scan())
        with self.assertRaises(ValidationError) as caught:
            confirm_scan(
                scan=scan, values=dict(CONFIRMED), actor=self.lawyer, assigned_lawyer=self.lawyer
            )

        self.assertIn("Someone Else", str(caught.exception.detail["pid"]))
        self.assertEqual(Client.objects.count(), 1)
        self.assertFalse(Document.objects.exists())
        # The scan is untouched, so the lawyer can correct the number and confirm again.
        scan.refresh_from_db()
        self.assertFalse(scan.is_confirmed)
        self.assertTrue((settings.DOCUMENTS_ROOT / scan.file_path).exists())

    def test_creating_a_client_needs_the_identity_fields(self):
        scan = self._read(self._scan())
        with self.assertRaises(ValidationError) as caught:
            confirm_scan(
                scan=scan,
                values={"full_name": "Only A Name"},
                actor=self.lawyer,
                assigned_lawyer=self.lawyer,
            )
        self.assertIn("pid", caught.exception.detail)

    def test_a_new_case_needs_an_assigned_lawyer(self):
        scan = self._read(self._scan())
        with self.assertRaises(ValidationError):
            confirm_scan(scan=scan, values=dict(CONFIRMED), actor=self.lawyer)

    def test_a_card_cannot_be_confirmed_twice(self):
        scan = self._read(self._scan())
        confirm_scan(
            scan=scan, values=dict(CONFIRMED), actor=self.lawyer, assigned_lawyer=self.lawyer
        )
        with self.assertRaises(ValidationError):
            confirm_scan(
                scan=scan, values=dict(CONFIRMED), actor=self.lawyer, assigned_lawyer=self.lawyer
            )
        self.assertEqual(Document.objects.count(), 1)


class ConfirmOntoAnExistingClientTests(ScanTestBase):
    def setUp(self):
        super().setUp()
        self.client_row = make_client(
            full_name="Old Name", pid="OLD-1", mother_full_name="Old M", marital_status="married",
            spouse_name="Spouse", spouse_mother_full_name="SM", spouse_date_of_birth=date(1990, 1, 1),
        )
        self.process = create_process(
            client=self.client_row, assigned_lawyer=self.lawyer, actor=self.admin
        )

    def test_a_replacement_scan_updates_the_client_it_is_confirmed_onto(self):
        scan = self._read(self._scan())
        confirm_scan(
            scan=scan,
            values=dict(CONFIRMED),
            client=self.client_row,
            client_version=self.client_row.version,
            actor=self.lawyer,
        )
        self.client_row.refresh_from_db()
        self.assertEqual(self.client_row.pid, "200103487811")
        self.assertEqual(Client.objects.count(), 1)

    def test_a_spouse_card_fills_the_spouse_columns(self):
        scan = self._read(self._scan(document_type="SpouseID"))
        confirm_scan(
            scan=scan,
            values={
                "full_name": "Spouse Name",
                "mother_full_name": "Spouse Mother",
                "date_of_birth": date(1995, 3, 4),
            },
            client=self.client_row,
            client_version=self.client_row.version,
            actor=self.lawyer,
        )
        self.client_row.refresh_from_db()
        self.assertEqual(self.client_row.spouse_name, "Spouse Name")
        self.assertEqual(self.client_row.spouse_mother_full_name, "Spouse Mother")
        self.assertEqual(self.client_row.spouse_date_of_birth, date(1995, 3, 4))
        # A spouse's own PID is not stored — the client's is the identity key (§3.7).
        self.assertEqual(self.client_row.pid, "OLD-1")

    def test_a_spouse_card_cannot_create_a_client(self):
        scan = self._read(self._scan(document_type="SpouseID"))
        with self.assertRaises(ValidationError):
            confirm_scan(
                scan=scan, values=dict(CONFIRMED), actor=self.lawyer, assigned_lawyer=self.lawyer
            )

    def test_a_stale_client_version_is_rejected(self):
        scan = self._read(self._scan())
        with self.assertRaises(StaleVersion):
            confirm_scan(
                scan=scan,
                values=dict(CONFIRMED),
                client=self.client_row,
                client_version=self.client_row.version + 5,
                actor=self.lawyer,
            )

    def test_only_the_confirmed_columns_are_written(self):
        """A full save() would write back every column, including stale copies of fields the
        review screen never loaded — silently undoing a concurrent edit on the same record."""
        scan = self._read(self._scan())
        written = {}
        original = Client.save

        def spy(instance, *args, **kwargs):
            written.update(kwargs)
            return original(instance, *args, **kwargs)

        with mock.patch.object(Client, "save", spy):
            confirm_scan(
                scan=scan,
                values={"mother_full_name": "New Mother"},
                client=self.client_row,
                client_version=self.client_row.version,
                actor=self.lawyer,
            )
        self.assertEqual(
            set(written["update_fields"]), {"mother_full_name", "version", "updated_at"}
        )

    def test_confirming_does_not_lock_the_fields(self):
        """Confirming records that a human checked it; the data stays editable afterwards."""
        scan = self._read(self._scan())
        confirm_scan(
            scan=scan,
            values={"full_name": "First Value"},
            client=self.client_row,
            client_version=self.client_row.version,
            actor=self.lawyer,
        )
        self.client_row.refresh_from_db()
        self.client_row.full_name = "Changed Later"
        self.client_row.save(update_fields=["full_name"])
        self.client_row.refresh_from_db()
        self.assertEqual(self.client_row.full_name, "Changed Later")


class SweepTests(ScanTestBase):
    """§6.3: the DB is the source of truth for status, so something has to notice when the broker
    loses a task — and a staged ID nobody confirmed must not sit in the store for good."""

    def _age(self, scan, **delta):
        old = timezone.now() - timedelta(**delta)
        CardScan.objects.filter(pk=scan.pk).update(created_at=old, updated_at=old)
        return scan

    def test_a_reading_whose_task_vanished_is_re_enqueued(self):
        scan = self._age(self._scan(), hours=2)
        # The task is queued on commit so the worker can never read an uncommitted row; in a test
        # the surrounding transaction never commits, so the callbacks have to be run explicitly.
        with mock.patch("ocr.tasks.read_card_scan.delay") as delay:
            with self.captureOnCommitCallbacks(execute=True):
                requeued = sweep.requeue_stuck_scans()

        self.assertEqual(requeued, [scan.pk])
        delay.assert_called_once_with(scan.pk)
        scan.refresh_from_db()
        self.assertEqual(scan.status, CardScan.Status.PENDING)

    def test_a_reading_still_in_flight_is_left_alone(self):
        self._scan()
        with mock.patch("ocr.tasks.read_card_scan.delay") as delay:
            with self.captureOnCommitCallbacks(execute=True):
                self.assertEqual(sweep.requeue_stuck_scans(), [])
        delay.assert_not_called()

    def test_a_finished_reading_is_never_re_enqueued(self):
        scan = self._age(self._read(self._scan()), hours=2)
        self.assertEqual(sweep.requeue_stuck_scans(), [])

    def test_an_abandoned_scan_loses_its_file_but_keeps_its_row(self):
        scan = self._age(self._read(self._scan()), days=30)
        path = settings.DOCUMENTS_ROOT / scan.file_path

        discarded = sweep.discard_abandoned_scans()

        self.assertEqual(discarded, [scan.pk])
        self.assertFalse(path.exists())
        scan.refresh_from_db()
        self.assertIsNotNone(scan.discarded_at)
        self.assertEqual(scan.file_path, "")
        self.assertTrue(
            ActivityLog.objects.filter(
                entity_type="CardScan", entity_id=str(scan.pk),
                action=ActivityLog.Action.DELETE,
            ).exists()
        )

    def test_a_recent_scan_is_not_discarded(self):
        scan = self._age(self._read(self._scan()), days=1)
        self.assertEqual(sweep.discard_abandoned_scans(), [])
        self.assertTrue((settings.DOCUMENTS_ROOT / scan.file_path).exists())

    def test_a_confirmed_scan_is_never_touched(self):
        scan = self._read(self._scan())
        confirm_scan(
            scan=scan, values=dict(CONFIRMED), actor=self.lawyer, assigned_lawyer=self.lawyer
        )
        self._age(scan, days=90)

        self.assertEqual(sweep.discard_abandoned_scans(), [])
        document = Document.objects.get()
        self.assertTrue((settings.DOCUMENTS_ROOT / document.file_path).exists())

    def test_the_command_runs_and_reports(self):
        self._age(self._read(self._scan()), days=30)
        out = StringIO()
        call_command("sweep_card_scans", stdout=out)
        self.assertIn("discarded 1", out.getvalue())


class ScanApiTests(ScanTestBase):
    def test_staging_through_the_api_returns_202(self):
        self.client.force_authenticate(self.lawyer)
        response = self.client.post(
            reverse("card-scan-list"),
            {
                "document_type": "ClientID",
                "file": SimpleUploadedFile("id.pdf", make_pdf(), content_type="application/pdf"),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.data["status"], CardScan.Status.PENDING)

    def test_a_lawyer_cannot_see_another_lawyers_unconfirmed_scan(self):
        """An unconfirmed scan is a citizen's ID card with no case attached to gate it yet."""
        scan = self._read(self._scan())
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(reverse("card-scan-detail", args=[scan.id])).status_code, 404)

    def test_an_admin_can_see_any_scan(self):
        scan = self._read(self._scan())
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get(reverse("card-scan-detail", args=[scan.id])).status_code, 200)

    def test_the_staged_pdf_is_served_for_the_preview_pane(self):
        scan = self._read(self._scan())
        self.client.force_authenticate(self.lawyer)
        response = self.client.get(reverse("card-scan-file", args=[scan.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")

    def test_confirming_through_the_api_creates_everything(self):
        scan = self._read(self._scan())
        self.client.force_authenticate(self.lawyer)
        response = self.client.post(
            reverse("card-scan-confirm", args=[scan.id]),
            {
                "pid": "200103487811",
                "full_name": "محمد رعد",
                "mother_full_name": "دلسوز على",
                "date_of_birth": "2001-08-12",
                "assigned_lawyer": self.lawyer.id,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.data["confirmed_at"])
        self.assertEqual(Client.objects.get().pid, "200103487811")

    def test_updating_an_existing_client_requires_its_version(self):
        client_row = make_client(full_name="X", pid="X-1", mother_full_name="M")
        create_process(client=client_row, assigned_lawyer=self.lawyer, actor=self.admin)
        scan = self._read(self._scan())
        self.client.force_authenticate(self.lawyer)
        response = self.client.post(
            reverse("card-scan-confirm", args=[scan.id]),
            {"full_name": "Y", "client": client_row.id},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("client_version", response.data)

    def test_a_non_assignee_cannot_file_onto_someone_elses_case(self):
        client_row = make_client(full_name="X", pid="X-2", mother_full_name="M")
        create_process(client=client_row, assigned_lawyer=self.lawyer, actor=self.admin)
        scan = self._read(self._scan(actor=self.other))
        self.client.force_authenticate(self.other)
        response = self.client.post(
            reverse("card-scan-confirm", args=[scan.id]),
            {"full_name": "Y", "client": client_row.id, "client_version": client_row.version},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
