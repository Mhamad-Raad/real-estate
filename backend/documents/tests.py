"""Document upload/download/validation + file-store safety + step recompute (§4.4, §6.7)."""

import tempfile
from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from catalog.models import Category
from clients.models import Client
from common.models import ActivityLog
from processes.models import ProcessStep
from processes.services import create_process

from . import filestore
from .models import Document


def pdf_file(name="id.pdf", body=b"%PDF-1.4 minimal test pdf"):
    return SimpleUploadedFile(name, body, content_type="application/pdf")


@override_settings(DOCUMENTS_ROOT=Path(tempfile.mkdtemp()))
class DocumentApiTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user("adm", password="pw12345678", role=User.Role.ADMIN)
        self.lawyer = User.objects.create_user("lw", password="pw12345678")
        self.other = User.objects.create_user("lw2", password="pw12345678")
        self.category = Category.objects.create(code="A", name="Cat A")
        self.client_row = Client.objects.create(
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

    def test_upload_creates_row_and_writes_file(self):
        self.client.force_authenticate(self.lawyer)
        resp = self._upload()
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        doc = Document.objects.get(pk=resp.data["id"])
        self.assertTrue((settings.DOCUMENTS_ROOT / doc.file_path).exists())
        self.assertIn("ClientID", doc.display_filename)
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
        self.assertEqual(filestore.sanitize("ئەحمەد محمد"), "ئەحمەد_محمد")  # Sorani survives
        self.assertEqual(filestore.sanitize(""), "NA")

    def test_display_name_composition(self):
        name = filestore.compose_display_name(
            category_code="A", institute="General", person_name="Ahmad Ali",
            document_type="ClientID", sid="7f3ae2ab",
        )
        self.assertEqual(name, "A_General_Ahmad_Ali_ClientID__7f3ae2ab.pdf")

    def test_looks_like_pdf(self):
        self.assertTrue(filestore.looks_like_pdf(b"%PDF-1.7 ..."))
        self.assertFalse(filestore.looks_like_pdf(b"GIF89a"))
