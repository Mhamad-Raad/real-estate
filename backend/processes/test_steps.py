"""Per-step save, institute-entry validation, end-date auto-set, and Step-5 completion (§5)."""

import tempfile
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from catalog.models import Category
from clients.models import Client

from .models import ProcessInstituteEntry, ProcessStep
from .services import create_process


@override_settings(DOCUMENTS_ROOT=Path(tempfile.mkdtemp()))
class WorkflowApiTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user("adm", password="pw12345678", role=User.Role.ADMIN)
        self.lawyer = User.objects.create_user("lw", password="pw12345678")
        self.category = Category.objects.create(code="A", name="A")
        self.client_row = Client.objects.create(
            full_name="Person", pid="111", mother_full_name="Mother", category=self.category
        )
        self.process = create_process(
            client=self.client_row, assigned_lawyer=self.lawyer, actor=self.lawyer,
            category=self.category,
        )
        self.client.force_authenticate(self.lawyer)

    def _upload(self, step, doc_type, entry=None):
        body = {"process": self.process.id, "step_number": step, "document_type": doc_type,
                "file": SimpleUploadedFile("f.pdf", b"%PDF-1.4 x", content_type="application/pdf")}
        if entry:
            body["institute_entry"] = entry
        return self.client.post(reverse("document-list"), body, format="multipart")

    def test_step_save_requires_version_and_recomputes(self):
        url = reverse("process-steps", args=[self.process.id, 2])
        step2 = ProcessStep.objects.get(process=self.process, step_number=2)
        resp = self.client.patch(url, {"start_date": "2026-07-01", "version": step2.version}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        step2.refresh_from_db()
        self.assertEqual(str(step2.start_date), "2026-07-01")
        self.assertEqual(step2.status, ProcessStep.Status.IN_PROGRESS)  # data but not complete

    def test_institute_entry_rejects_wrong_step_code(self):
        # A Step-2 code cannot be filed under Step 3.
        resp = self.client.post(
            reverse("institute-entry-list"),
            {"process": self.process.id, "step_number": 3, "institute_code": "INST_S2_A"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_duplicate_fixed_institute_rejected(self):
        body = {"process": self.process.id, "step_number": 2, "institute_code": "INST_S2_A"}
        first = self.client.post(reverse("institute-entry-list"), body, format="json")
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        dup = self.client.post(reverse("institute-entry-list"), body, format="json")
        self.assertEqual(dup.status_code, status.HTTP_400_BAD_REQUEST)  # not a 500

    def test_completed_process_reverts_when_a_step_is_reopened(self):
        # Complete the whole case (admin force), then break Step 2 and confirm it drops to in_progress.
        self.client.force_authenticate(self.admin)
        self.process.refresh_from_db()
        self.client.post(
            reverse("process-complete", args=[self.process.id]),
            {"force": True, "version": self.process.version}, format="json",
        )
        self.process.refresh_from_db()
        self.assertEqual(self.process.overall_status, "complete")
        # Reopen Step 2 by clearing its start_date via a save → recompute makes it incomplete.
        step2 = ProcessStep.objects.get(process=self.process, step_number=2)
        self.client.patch(
            reverse("process-steps", args=[self.process.id, 2]),
            {"start_date": None, "version": step2.version}, format="json",
        )
        self.process.refresh_from_db()
        self.assertEqual(self.process.overall_status, "in_progress")

    def test_step2_approval_autosets_end_date(self):
        entry = self.client.post(
            reverse("institute-entry-list"),
            {"process": self.process.id, "step_number": 2, "institute_code": "INST_S2_A",
             "assigned_lawyer": self.lawyer.id, "approval_status": "approved"},
            format="json",
        )
        self.assertEqual(entry.status_code, status.HTTP_201_CREATED)
        step2 = ProcessStep.objects.get(process=self.process, step_number=2)
        self.assertIsNotNone(step2.end_date)  # auto-set on approval (§5.8)

    def test_step4_completes_when_both_institutes_have_doc_and_lawyer(self):
        for code in ("INST_S4_A", "INST_S4_B"):
            e = self.client.post(
                reverse("institute-entry-list"),
                {"process": self.process.id, "step_number": 4, "institute_code": code,
                 "assigned_lawyer": self.lawyer.id},
                format="json",
            )
            self._upload(4, "ApprovalLetter", entry=e.data["id"])
        step4 = ProcessStep.objects.get(process=self.process, step_number=4)
        self.assertEqual(step4.status, ProcessStep.Status.COMPLETE)

    def test_complete_blocks_on_missing_then_admin_can_force(self):
        url = reverse("process-complete", args=[self.process.id])
        # Nothing is complete → lawyer completion blocked (400).
        blocked = self.client.post(url, {"version": self.process.version}, format="json")
        self.assertEqual(blocked.status_code, status.HTTP_400_BAD_REQUEST)
        # Lawyer cannot force.
        forced_by_lawyer = self.client.post(url, {"force": True, "version": self.process.version}, format="json")
        self.assertEqual(forced_by_lawyer.status_code, status.HTTP_403_FORBIDDEN)
        # Admin can force.
        self.client.force_authenticate(self.admin)
        self.process.refresh_from_db()
        forced = self.client.post(url, {"force": True, "version": self.process.version}, format="json")
        self.assertEqual(forced.status_code, status.HTTP_200_OK)
        self.assertEqual(forced.data["overall_status"], "complete")
