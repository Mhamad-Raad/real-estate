"""Document upload/download/validation + file-store safety + step recompute (§4.4, §6.7)."""

import tempfile
from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from pypdf import PdfReader
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from catalog.models import Category
from clients.models import Client
from common.models import ActivityLog
from processes.models import ProcessStep
from processes.services import create_process

from . import filestore
from .factories import make_pdf
from .models import Document
from .services import create_document
from clients.factories import make_client


def pdf_file(name="id.pdf", body=None):
    body = make_pdf() if body is None else body
    return SimpleUploadedFile(name, body, content_type="application/pdf")


@override_settings(DOCUMENTS_ROOT=Path(tempfile.mkdtemp()))
class DocumentApiTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user("adm", password="pw12345678", role=User.Role.ADMIN)
        self.lawyer = User.objects.create_user("lw", password="pw12345678")
        self.other = User.objects.create_user("lw2", password="pw12345678")
        self.category = Category.objects.create(code="A", name="Cat A")
        self.client_row = make_client(
            full_name="Ahmad Mohammed", pid="1990111", mother_full_name="Mother", category=self.category
        )
        self.process = create_process(
            client=self.client_row, assigned_lawyer=self.lawyer, actor=self.lawyer, category=self.category
        )

    def _upload(self, **over):
        body = {
            "process": self.process.id,
            "step_number": 1,
            "document_type": "ClientID",
            "file": pdf_file(),
            **over,
        }
        return self.client.post(reverse("document-list"), body, format="multipart")

    def _scanned_case_file(self):
        return create_document(
            process=self.process, step_number=5, document_type="CompiledCase",
            input_source=Document.InputSource.IMPORTED, content=make_pdf(1), actor=self.lawyer,
        )

    def test_a_lawyer_cannot_delete_the_scanned_case_file(self):
        """The backlog door's scan is the only copy of a paper case (UC-114); restore is an admin
        desk, so the delete is an admin's press too — enforced here, not by a hidden button."""
        scan = self._scanned_case_file()
        self.client.force_authenticate(self.lawyer)

        resp = self.client.delete(reverse("document-detail", args=[scan.id]))

        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        scan.refresh_from_db()
        self.assertFalse(scan.is_deleted)

    def test_an_admin_can_still_delete_it(self):
        scan = self._scanned_case_file()
        self.client.force_authenticate(self.admin)

        resp = self.client.delete(reverse("document-detail", args=[scan.id]))

        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)

    def test_upload_creates_row_and_writes_file(self):
        self.client.force_authenticate(self.lawyer)
        resp = self._upload()
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        doc = Document.objects.get(pk=resp.data["id"])
        self.assertTrue((settings.DOCUMENTS_ROOT / doc.file_path).exists())
        self.assertIn("ناسنامەی کڕیار", doc.display_filename)
        self.assertTrue(doc.display_filename.endswith(".pdf"))
        self.assertTrue(
            ActivityLog.objects.filter(entity_type="Document", entity_id=str(doc.id)).exists()
        )

    def test_rejects_non_pdf(self):
        self.client.force_authenticate(self.lawyer)
        resp = self.client.post(
            reverse("document-list"),
            {"process": self.process.id, "step_number": 1, "document_type": "ClientID",
             "file": SimpleUploadedFile("x.pdf", b"not a pdf", content_type="application/pdf")},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Document.objects.exists())

    def test_rejects_a_malformed_image_without_a_server_error(self):
        """Image bytes are converted on arrival (§6.7); a corrupt or hostile file is a bad upload,
        so it must read as 400 like any other, not as a 500 from deep inside the decoder."""
        self.client.force_authenticate(self.lawyer)
        resp = self.client.post(
            reverse("document-list"),
            {"process": self.process.id, "step_number": 1, "document_type": "ClientID",
             "file": SimpleUploadedFile(
                 "id.jpg", b"\xff\xd8\xff" + b"garbage" * 50, content_type="image/jpeg"
             )},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Document.objects.exists())

    def test_scanned_multipage_upload_is_filed_and_recorded_as_scanned(self):
        """The camera path (§6.1) assembles the pages in the browser and posts the finished PDF
        to this same endpoint — it differs from an import only in what the row says it is."""
        self.client.force_authenticate(self.lawyer)
        # Not a card: a card slot holds two sides and no more (UC-085), and what this pins is
        # that the camera path keeps every page it captured, whatever paper it is capturing.
        resp = self._upload(
            document_type="SignedAgreement",
            file=pdf_file("scan.pdf", make_pdf(pages=3)),
            input_source=Document.InputSource.SCANNED,
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        doc = Document.objects.get(pk=resp.data["id"])
        self.assertEqual(doc.input_source, Document.InputSource.SCANNED)
        # Every captured page survives the trip; a scan that quietly loses pages is a lost record.
        stored = PdfReader(settings.DOCUMENTS_ROOT / doc.file_path)
        self.assertEqual(len(stored.pages), 3)

    def test_upload_without_an_input_source_is_an_import(self):
        self.client.force_authenticate(self.lawyer)
        resp = self._upload()
        self.assertEqual(
            Document.objects.get(pk=resp.data["id"]).input_source,
            Document.InputSource.IMPORTED,
        )

    def test_an_upload_cannot_claim_to_be_system_generated(self):
        """`system_generated` carries the 200 MB cap instead of the 25 MB upload cap (§12), so a
        user-supplied value must not be able to select it."""
        self.client.force_authenticate(self.lawyer)
        resp = self._upload(input_source=Document.InputSource.SYSTEM_GENERATED)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Document.objects.exists())

    def test_oversize_rejected(self):
        self.client.force_authenticate(self.lawyer)
        with override_settings(MAX_UPLOAD_BYTES=10):
            resp = self._upload()
        self.assertEqual(resp.status_code, status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)

    def test_non_assignee_lawyer_cannot_upload(self):
        self.client.force_authenticate(self.other)
        self.assertEqual(self._upload().status_code, status.HTTP_403_FORBIDDEN)

    def test_download_serves_friendly_name(self):
        self.client.force_authenticate(self.lawyer)
        doc_id = self._upload().data["id"]
        resp = self.client.get(reverse("document-file", args=[doc_id]))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn(".pdf", resp["Content-Disposition"])

    def test_upload_recomputes_step_status(self):
        # Step 1 needs land_id + category + three doc types; after all three it should be complete.
        self.client.force_authenticate(self.lawyer)
        self.process.land_id = "L-1"
        self.process.save(update_fields=["land_id"])
        for doc_type in ("ClientID", "RealEstate", "SignedAgreement"):
            self._upload(document_type=doc_type)
        step1 = ProcessStep.objects.get(process=self.process, step_number=1)
        self.assertEqual(step1.status, ProcessStep.Status.COMPLETE)


class FileStoreUnitTests(APITestCase):
    def test_sanitize_strips_illegal_and_keeps_unicode(self):
        self.assertEqual(filestore.sanitize('a/b:c*d'), "abcd")
        # Sorani survives, and so do the spaces between its words — these names are read by
        # people browsing the folders, not parsed by anything (UC-060).
        self.assertEqual(filestore.sanitize("ئەحمەد محمد"), "ئەحمەد محمد")
        self.assertEqual(filestore.sanitize("ئەحمەد   محمد"), "ئەحمەد محمد")
        self.assertEqual(filestore.sanitize(""), "NA")

    def test_display_name_leads_with_the_case_code_and_names_the_paper(self):
        name = filestore.compose_display_name(
            unique_code="A18", category_code="A", person_name="Ahmad Ali",
            label=filestore.document_label("ClientID"),
        )
        self.assertEqual(name, "A18_Ahmad Ali_ناسنامەی کڕیار.pdf")

    def test_display_name_falls_back_to_the_category_when_a_case_predates_codes(self):
        name = filestore.compose_display_name(
            unique_code="", category_code="A", person_name="Ahmad Ali",
            label=filestore.document_label("ClientID"),
        )
        self.assertEqual(name, "A_Ahmad Ali_ناسنامەی کڕیار.pdf")

    def test_a_second_file_in_one_slot_is_numbered_not_hashed(self):
        """UC-097: the office browses this archive in Explorer, and an 8-character hex suffix on
        every file made it unreadable. Two papers legitimately share the `RealEstate` slot
        (UC-055), so the second is numbered the way Windows numbers a repeated copy."""
        label = filestore.document_label("RealEstate")
        self.assertEqual(label, "فۆرم و نووسراوی شارەوانی")
        directory = filestore.case_directory(
            category_code="A", unique_code="A18", pid="199036880522"
        )
        keys = dict(directory=directory, label=label)

        first = filestore.reserve_stored_name(**keys)
        second = filestore.reserve_stored_name(**keys)
        third = filestore.reserve_stored_name(**keys)

        self.assertEqual(first.name, "فۆرم و نووسراوی شارەوانی.pdf")
        self.assertEqual(second.name, "فۆرم و نووسراوی شارەوانی (2).pdf")
        self.assertEqual(third.name, "فۆرم و نووسراوی شارەوانی (3).pdf")
        self.assertEqual(str(first.parent), "A/A18_199036880522")

    def test_reserving_a_name_claims_it_so_a_concurrent_filing_cannot_take_it(self):
        """The name is claimed by creating the file, not by looking at the folder — two lawyers
        filing the same slot at once would otherwise both see the same slot free."""
        keys = dict(
            directory=filestore.case_directory(
                category_code="A", unique_code="A19", pid="199036880523"
            ),
            label=filestore.document_label("ClientID"),
        )
        rel = filestore.reserve_stored_name(**keys)
        self.assertTrue((settings.DOCUMENTS_ROOT / rel).exists())
        self.assertNotEqual(filestore.reserve_stored_name(**keys), rel)

    def test_the_case_folder_is_keyed_by_code_and_pid(self):
        rel = filestore.relative_path(
            category_code="A", unique_code="A18", pid="199036880522", stored_filename="x.pdf"
        )
        self.assertEqual(str(rel), "A/A18_199036880522/x.pdf")
        # A case opened before codes existed keeps the plain PID folder it already had.
        plain = filestore.relative_path(
            category_code="A", unique_code="", pid="199036880522", stored_filename="x.pdf"
        )
        self.assertEqual(str(plain), "A/199036880522/x.pdf")

    def test_looks_like_pdf(self):
        self.assertTrue(filestore.looks_like_pdf(b"%PDF-1.7 ..."))
        # Magic bytes alone are not enough — a truncated scan passes that and is unreadable.
        self.assertFalse(filestore.is_readable_pdf(b"%PDF-1.7 truncated"))
        self.assertTrue(filestore.is_readable_pdf(make_pdf()))
        self.assertFalse(filestore.looks_like_pdf(b"GIF89a"))


class DocumentTypeVocabularyTests(APITestCase):
    """`document_type` is a controlled vocabulary (§6.7) — enforced on write, not just in the UI."""

    def setUp(self):
        self.lawyer = User.objects.create_user("vlw2", password="pw12345678")
        self.category = Category.objects.create(code="V", name="V")
        self.client_row = make_client(pid="VOC-1", category=self.category)
        self.process = create_process(
            client=self.client_row, assigned_lawyer=self.lawyer, actor=self.lawyer,
            category=self.category,
        )
        self.client.force_authenticate(self.lawyer)

    def _post(self, document_type):
        return self.client.post(
            reverse("document-list"),
            {
                "process": self.process.id,
                "step_number": 1,
                "document_type": document_type,
                "file": SimpleUploadedFile(
                    "f.pdf", make_pdf(), content_type="application/pdf"
                ),
            },
            format="multipart",
        )

    def test_unknown_document_type_is_rejected(self):
        """Otherwise the file is stored under a label no step wants and no slot renders."""
        resp = self._post("NotARealType")

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("document_type", resp.data)

    def test_known_document_type_is_accepted(self):
        resp = self._post("ClientID")

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)


class BulkJobFilenameTests(APITestCase):
    """A generated list is named for what it is (§6.7, UC-066).

    The endpoint used to answer `list_<id>.pdf` for **every** kind, so a code list arrived called
    a case list. The name belongs on the server, like every other filename in this system.
    """

    def test_each_kind_is_named_for_itself(self):
        from documents.filestore import bulk_job_filename
        from documents.models import GenerationJob

        class FakeJob:
            def __init__(self, kind, pk):
                self.kind, self.id = kind, pk

        self.assertEqual(
            bulk_job_filename(FakeJob(GenerationJob.Kind.PROCESS_CODES, 33)),
            "لیستی کۆدەکان_33.pdf",
        )
        self.assertEqual(
            bulk_job_filename(FakeJob(GenerationJob.Kind.PROCESS_LIST, 29)),
            "لیستی کەیسەکان_29.pdf",
        )

    def test_an_unknown_kind_still_gets_a_name(self):
        from documents.filestore import bulk_job_filename

        class FakeJob:
            kind, id = "something_new", 4

        self.assertEqual(bulk_job_filename(FakeJob()), "بەڵگەنامە_4.pdf")
