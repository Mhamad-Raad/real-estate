"""Review probes for the 2026-08-03 batches (12 & 13) — run before the office tests again."""

import tempfile
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from catalog.models import Category
from clients.factories import client_data, make_client
from documents.factories import make_pdf

from .models import ProcessStep
from .services import create_process
from .status import compute_step_status


@override_settings(DOCUMENTS_ROOT=Path(tempfile.mkdtemp()))
class IntakeLeavesNoStaleStepTests(APITestCase):
    """`land_id` is a Step-4 requirement now, so intake must not leave step 4 stale (UC-041)."""

    def setUp(self):
        self.lawyer = User.objects.create_user("stale_lw", password="pw12345678")
        self.category = Category.objects.create(code="A", name="A")
        self.client.force_authenticate(self.lawyer)

    def test_a_case_created_with_a_land_id_has_no_stale_step_status(self):
        payload = {
            "client_data": client_data(pid="199001010101"),
            "category": self.category.id,
            "land_id": "PLOT-9",
        }
        resp = self.client.post(reverse("process-list"), payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        from .models import Process

        process = Process.objects.prefetch_related(
            "steps", "documents", "institute_entries"
        ).get(pk=resp.data["id"])
        for row in process.steps.all():
            self.assertEqual(
                row.status,
                compute_step_status(process, row.step_number, row),
                f"step {row.step_number} stored status is stale right after intake",
            )


@override_settings(DOCUMENTS_ROOT=Path(tempfile.mkdtemp()))
class AssignableLawyerDoesNotBreakExistingRowsTests(APITestCase):
    """Tightening who may be assigned must not lock existing rows out of ordinary edits (UC-035)."""

    def setUp(self):
        self.admin = User.objects.create_user(
            "rev_admin", password="pw12345678", role=User.Role.ADMIN
        )
        self.leaver = User.objects.create_user("rev_leaver", password="pw12345678")
        self.category = Category.objects.create(code="B", name="B")
        self.client_row = make_client(full_name="P", pid="197001011111", category=self.category)
        self.process = create_process(
            client=self.client_row,
            assigned_lawyer=self.leaver,
            actor=self.admin,
            category=self.category,
        )
        self.client.force_authenticate(self.admin)

    def test_an_entry_assigned_to_someone_who_then_left_can_still_be_edited(self):
        entry = self.client.post(
            reverse("institute-entry-list"),
            {
                "process": self.process.id,
                "step_number": 2,
                "institute_code": "INST_S2_A",
                "assigned_lawyer": self.leaver.id,
            },
            format="json",
        )
        self.assertEqual(entry.status_code, status.HTTP_201_CREATED)

        self.leaver.is_active = False
        self.leaver.save(update_fields=["is_active"])

        # The office still has to be able to record the approval on a row whose assignee has left.
        resp = self.client.patch(
            reverse("institute-entry-detail", args=[entry.data["id"]]),
            {"approval_status": "approved", "version": entry.data["version"]},
            format="json",
        )
        self.assertEqual(
            resp.status_code,
            status.HTTP_200_OK,
            "an entry whose assignee has since left became uneditable",
        )

    def test_a_step_4_document_upload_re_derives_the_step(self):
        """The real-estate paper moved to step 4 — uploading it must update that step (UC-037)."""
        self.process.land_id = "L-9"
        self.process.save(update_fields=["land_id"])
        before = ProcessStep.objects.get(process=self.process, step_number=4).status
        self.client.post(
            reverse("document-list"),
            {
                "process": self.process.id,
                "step_number": 4,
                "document_type": "RealEstate",
                "file": SimpleUploadedFile("f.pdf", make_pdf(), content_type="application/pdf"),
            },
            format="multipart",
        )
        row = ProcessStep.objects.get(process=self.process, step_number=4)
        self.assertNotEqual(row.status, before)
        self.assertEqual(
            row.status,
            compute_step_status(
                self.process, 4, row
            ),
        )
