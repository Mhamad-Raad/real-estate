"""Per-step save, institute-entry validation, end-date auto-set, and Step-5 completion (§5)."""

from datetime import date

import tempfile
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile

from documents.factories import make_pdf
from django.db import connection
from django.utils import timezone
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from catalog.models import Category
from clients.models import Client

from .models import ProcessInstituteEntry, ProcessStep
from .services import create_process, recompute_step
from catalog.institutes import codes_for_step

from .status import missing_requirements
from clients.factories import make_client


@override_settings(DOCUMENTS_ROOT=Path(tempfile.mkdtemp()))
class WorkflowApiTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user("adm", password="pw12345678", role=User.Role.ADMIN)
        self.lawyer = User.objects.create_user("lw", password="pw12345678")
        self.category = Category.objects.create(code="A", name="A")
        self.client_row = make_client(
            full_name="Person", pid="111", mother_full_name="Mother", category=self.category
        )
        self.process = create_process(
            client=self.client_row, assigned_lawyer=self.lawyer, actor=self.lawyer,
            category=self.category,
        )
        self.client.force_authenticate(self.lawyer)

    def _upload(self, step, doc_type, entry=None):
        body = {"process": self.process.id, "step_number": step, "document_type": doc_type,
                "file": SimpleUploadedFile("f.pdf", make_pdf(), content_type="application/pdf")}
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

    def test_step_2_completes_on_its_single_institute(self):
        """Step 2 demanded two institutes when only one exists, so it could never complete (UC-040)."""
        self.assertEqual(codes_for_step(2), ["INST_S2_A"])
        entry = self.client.post(
            reverse("institute-entry-list"),
            {"process": self.process.id, "step_number": 2, "institute_code": "INST_S2_A",
             "assigned_lawyer": self.lawyer.id, "approval_status": "approved"},
            format="json",
        )
        self._upload(2, "InstituteDoc", entry=entry.data["id"])
        step2 = ProcessStep.objects.get(process=self.process, step_number=2)
        self.client.patch(
            reverse("process-steps", args=[self.process.id, 2]),
            {"start_date": "2026-07-01", "version": step2.version}, format="json",
        )
        step2.refresh_from_db()
        self.assertEqual(step2.status, ProcessStep.Status.COMPLETE)

    def test_the_retired_step_2_code_is_refused(self):
        resp = self.client.post(
            reverse("institute-entry-list"),
            {"process": self.process.id, "step_number": 2, "institute_code": "INST_S2_B"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_step4_completes_on_institutes_plus_the_land_id_and_real_estate_paper(self):
        for code in ("INST_S4_A", "INST_S4_B"):
            e = self.client.post(
                reverse("institute-entry-list"),
                {"process": self.process.id, "step_number": 4, "institute_code": code,
                 "assigned_lawyer": self.lawyer.id},
                format="json",
            )
            self._upload(4, "InstituteDoc", entry=e.data["id"])
        step4 = ProcessStep.objects.get(process=self.process, step_number=4)
        # The institutes alone are no longer enough — the land number and the paper they produce
        # are Step-4 requirements now (UC-037, UC-041).
        self.assertEqual(step4.status, ProcessStep.Status.IN_PROGRESS)

        self.process.refresh_from_db()
        self.client.patch(
            reverse("process-detail", args=[self.process.id]),
            {"land_id": "PLOT-1", "version": self.process.version},
            format="json",
        )
        self._upload(4, "RealEstate")
        step4.refresh_from_db()
        self.assertEqual(step4.status, ProcessStep.Status.COMPLETE)

    def test_detail_query_count_does_not_grow_with_the_case(self):
        # The per-step `missing` lists must come out of prefetched collections, not one query per
        # step — otherwise every document or institute entry added makes the page slower (§3.6).
        url = reverse("process-detail", args=[self.process.id])

        def add(step, code, doc_type):
            entry = self.client.post(
                reverse("institute-entry-list"),
                {"process": self.process.id, "step_number": step, "institute_code": code,
                 "assigned_lawyer": self.lawyer.id},
                format="json",
            )
            self._upload(step, doc_type, entry=entry.data["id"])

        # Measure a case that already has one of everything, so fixed prefetch costs are paid…
        self._upload(1, "ClientID")
        add(2, "INST_S2_A", "InstituteDoc")
        self.client.get(url)  # warm any one-off caches so the measurements are comparable
        with CaptureQueriesContext(connection) as small_case:
            self.client.get(url)

        # …then triple the rows it has to walk. A prefetched read stays flat; an N+1 grows.
        for doc_type in ("RealEstate", "SignedAgreement"):
            self._upload(1, doc_type)
        add(3, "INST_S3_A", "InstituteDoc")
        add(4, "INST_S4_A", "InstituteDoc")
        add(4, "INST_S4_B", "InstituteDoc")

        with CaptureQueriesContext(connection) as big_case:
            resp = self.client.get(url)
        self.assertEqual(len(resp.data["documents"]), 7)
        self.assertEqual(
            len(big_case), len(small_case),
            f"detail grew from {len(small_case)} to {len(big_case)} queries as the case filled up",
        )

    def test_uploading_a_paper_re_derives_step_1_status(self):
        # Step 1 completes on the category + the client papers. `land_id` and the real-estate
        # paper are NOT among them — they belong to Step 4 now (UC-037, UC-041).
        step1 = ProcessStep.objects.get(process=self.process, step_number=1)
        self.assertNotEqual(step1.status, ProcessStep.Status.COMPLETE)
        for doc_type in ("ClientID", "SignedAgreement"):
            self._upload(1, doc_type)
        step1.refresh_from_db()
        self.assertEqual(step1.status, ProcessStep.Status.COMPLETE)

    def test_the_category_cannot_be_changed_after_the_case_is_created(self):
        """The office moves a case by deleting it and opening a new one, never by re-categorising
        it (UC-059). Refused outright rather than dropped, or the caller would get a 200 and
        believe it worked — and after UC-056 the code's first letter *is* the category."""
        other = Category.objects.create(code="Z", name="Z")
        self.process.refresh_from_db()
        resp = self.client.patch(
            reverse("process-detail", args=[self.process.id]),
            {"category": other.id, "version": self.process.version},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("category", resp.data)
        self.process.refresh_from_db()
        self.assertEqual(self.process.category_id, self.category.id)

    def test_resending_the_unchanged_category_is_not_treated_as_a_change(self):
        """A client that echoes the whole header back must not be rejected for saying nothing new."""
        self.process.refresh_from_db()
        resp = self.client.patch(
            reverse("process-detail", args=[self.process.id]),
            {"category": self.category.id, "land_id": "PLOT-7", "version": self.process.version},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.process.refresh_from_db()
        self.assertEqual(self.process.land_id, "PLOT-7")

    def test_step_1_completes_without_a_land_id_or_a_real_estate_paper(self):
        """The office does not hold either when a case opens — demanding them blocked every case."""
        for doc_type in ("ClientID", "SignedAgreement"):
            self._upload(1, doc_type)
        step1 = ProcessStep.objects.get(process=self.process, step_number=1)
        self.assertEqual(step1.status, ProcessStep.Status.COMPLETE)
        self.assertEqual(self.process.land_id, "")
        missing = missing_requirements(self.process, 1, step1)
        self.assertNotIn("land_id", missing)
        self.assertNotIn("doc:RealEstate", missing)

    def test_step_4_now_owns_the_land_id_and_the_real_estate_paper(self):
        step4 = ProcessStep.objects.get(process=self.process, step_number=4)
        missing = missing_requirements(self.process, 4, step4)
        self.assertIn("land_id", missing)
        self.assertIn("doc:RealEstate", missing)

        self.process.land_id = "PLOT-1"
        self.process.save(update_fields=["land_id"])
        self._upload(4, "RealEstate")
        self.process.refresh_from_db()
        missing = missing_requirements(self.process, 4, step4)
        self.assertNotIn("land_id", missing)
        self.assertNotIn("doc:RealEstate", missing)
        # The institutes are still required — the new rules add to Step 4, they do not replace it.
        self.assertIn("institute:INST_S4_A", missing)

    def test_clearing_the_land_id_re_derives_step_4_not_step_1(self):
        """The header PATCH must recompute Step 4 too, or its badge goes stale (UC-041)."""
        self.process.land_id = "PLOT-1"
        self.process.save(update_fields=["land_id"])
        self.process.refresh_from_db()
        resp = self.client.patch(
            reverse("process-detail", args=[self.process.id]),
            {"land_id": "", "version": self.process.version},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        detail = self.client.get(reverse("process-detail", args=[self.process.id]))
        missing = {s["step_number"]: s["missing"] for s in detail.data["steps"]}
        self.assertIn("land_id", missing[4])
        self.assertNotIn("land_id", missing[1])

    def test_override_re_derives_step_1_status(self):
        # A fired duplicate warning blocks Step 1; clearing it can be the last missing piece.
        self.process.duplicate_flagged = True
        self.process.save(update_fields=["duplicate_flagged"])
        for doc_type in ("ClientID", "SignedAgreement"):
            self._upload(1, doc_type)
        step1 = ProcessStep.objects.get(process=self.process, step_number=1)
        self.assertNotEqual(step1.status, ProcessStep.Status.COMPLETE)

        self.client.force_authenticate(self.admin)
        self.process.refresh_from_db()
        resp = self.client.post(
            reverse("process-override-duplicate", args=[self.process.id]),
            {"match_reason": "mother_name", "reason": "sibling", "version": self.process.version},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        step1.refresh_from_db()
        self.assertEqual(step1.status, ProcessStep.Status.COMPLETE)

    def test_complete_without_a_version_is_rejected(self):
        # Mark-complete is a write like any other — no version token, no lock, so 400 (§4.1).
        self.client.force_authenticate(self.admin)
        resp = self.client.post(
            reverse("process-complete", args=[self.process.id]), {"force": True}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.process.refresh_from_db()
        self.assertNotEqual(self.process.overall_status, "complete")

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

    def _finish_step_1(self):
        for doc_type in ("ClientID", "SignedAgreement"):
            self._upload(1, doc_type)

    def _finish_institute_step(self, step, codes, *, dated):
        """Take an institute step to complete the way the office does — through the API.

        Statuses cannot be forced with `update()` here: `complete_process` re-derives every step
        before it checks them, so a faked status is gone by the time it is read.
        """
        for code in codes:
            entry = self.client.post(
                reverse("institute-entry-list"),
                {"process": self.process.id, "step_number": step, "institute_code": code,
                 "assigned_lawyer": self.lawyer.id, "approval_status": "approved",
                 **({"approval_date": "2026-07-02"} if dated else {})},
                format="json",
            )
            self.assertEqual(entry.status_code, status.HTTP_201_CREATED, entry.data)
            self._upload(step, "InstituteDoc", entry=entry.data["id"])
        row = ProcessStep.objects.get(process=self.process, step_number=step)
        self.client.patch(
            reverse("process-steps", args=[self.process.id, step]),
            {"start_date": "2026-07-01", "version": row.version}, format="json",
        )

    def _ready_except_step_4(self):
        self._finish_step_1()
        self._finish_institute_step(2, codes_for_step(2), dated=False)
        self._finish_institute_step(3, codes_for_step(3), dated=True)
        self.process.refresh_from_db()
        for n in (1, 2, 3):
            self.assertEqual(
                ProcessStep.objects.get(process=self.process, step_number=n).status,
                ProcessStep.Status.COMPLETE,
                f"step {n} was not actually completed by the setup",
            )

    def test_step_4_does_not_hold_a_finished_case_open(self):
        """UC-079: not every allocation reaches the registration institutes, so an unfinished
        step 4 must not block the lawyer — and must not be quietly relabelled complete either."""
        self._ready_except_step_4()
        step4 = ProcessStep.objects.get(process=self.process, step_number=4)
        self.assertNotEqual(step4.status, ProcessStep.Status.COMPLETE)

        resp = self.client.post(
            reverse("process-complete", args=[self.process.id]),
            {"version": self.process.version}, format="json",
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data["overall_status"], "complete")
        # The step itself is left alone: it genuinely was not finished.
        step4.refresh_from_db()
        self.assertNotEqual(step4.status, ProcessStep.Status.COMPLETE)

    def test_an_unfinished_step_that_is_not_skippable_still_blocks(self):
        """Only step 4 is skippable — the guarantee would be worthless if it leaked to the rest."""
        self._ready_except_step_4()
        # Reopen step 3 by withdrawing its approvals — nothing here is ever hard-deleted (§11),
        # and an undecided institute is exactly what leaves the step outstanding.
        ProcessInstituteEntry.objects.filter(process=self.process, step_number=3).update(
            approval_status=ProcessInstituteEntry.ApprovalStatus.PENDING
        )
        recompute_step(self.process, 3)
        self.process.refresh_from_db()

        resp = self.client.post(
            reverse("process-complete", args=[self.process.id]),
            {"version": self.process.version}, format="json",
        )

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_closing_the_case_ends_the_final_step(self):
        """Nothing proceeds past step 5, so marking the case complete is what dates it (UC-078)."""
        self.client.force_authenticate(self.admin)
        step5 = ProcessStep.objects.get(process=self.process, step_number=5)
        self.assertIsNone(step5.end_date)

        url = reverse("process-complete", args=[self.process.id])
        resp = self.client.post(url, {"force": True, "version": self.process.version}, format="json")

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        step5.refresh_from_db()
        self.assertEqual(step5.end_date, timezone.now().date())

    def test_a_closing_date_entered_by_hand_survives_completion(self):
        """Same rule as every stamped date: a typed one is a correction, never overwritten."""
        self.client.force_authenticate(self.admin)
        entered = date(2026, 2, 17)
        ProcessStep.objects.filter(process=self.process, step_number=5).update(end_date=entered)

        url = reverse("process-complete", args=[self.process.id])
        resp = self.client.post(url, {"force": True, "version": self.process.version}, format="json")

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(
            ProcessStep.objects.get(process=self.process, step_number=5).end_date, entered
        )


@override_settings(DOCUMENTS_ROOT=Path(tempfile.mkdtemp()))
class AdvanceStepTests(APITestCase):
    """Progressive step unlocking — `current_step` is the highest step a lawyer may open (§5.2)."""

    def setUp(self):
        self.admin = User.objects.create_user("adm2", password="pw12345678", role=User.Role.ADMIN)
        self.lawyer = User.objects.create_user("lw2", password="pw12345678")
        self.other = User.objects.create_user("lw3", password="pw12345678")
        self.category = Category.objects.create(code="B", name="B")
        self.client_row = make_client(
            full_name="Person2", pid="222", mother_full_name="Mother2", category=self.category
        )
        self.process = create_process(
            client=self.client_row, assigned_lawyer=self.lawyer, actor=self.lawyer,
            category=self.category,
        )
        self.url = reverse("process-advance-step", args=[self.process.id])
        self.client.force_authenticate(self.lawyer)

    def _advance(self):
        self.process.refresh_from_db()
        return self.client.post(self.url, {"version": self.process.version}, format="json")

    def test_advance_unlocks_next_step_and_bumps_version(self):
        before = self.process.version
        resp = self._advance()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["current_step"], 2)
        self.process.refresh_from_db()
        self.assertEqual(self.process.version, before + 1)

    def test_advance_is_allowed_while_the_step_is_still_incomplete(self):
        # Step 1 has no documents, yet proceeding is a warning in the UI — never a server block.
        step1 = ProcessStep.objects.get(process=self.process, step_number=1)
        self.assertNotEqual(step1.status, ProcessStep.Status.COMPLETE)
        self.assertEqual(self._advance().status_code, status.HTTP_200_OK)

    def test_advance_stops_at_the_last_step(self):
        for expected in (2, 3, 4, 5):
            self.assertEqual(self._advance().data["current_step"], expected)
        self.assertEqual(self._advance().status_code, status.HTTP_400_BAD_REQUEST)

    def test_advance_requires_a_version_and_rejects_a_stale_one(self):
        self.assertEqual(
            self.client.post(self.url, {}, format="json").status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        stale = self.client.post(self.url, {"version": self.process.version + 5}, format="json")
        self.assertEqual(stale.status_code, status.HTTP_409_CONFLICT)

    def test_only_the_assigned_lawyer_or_an_admin_can_advance(self):
        self.client.force_authenticate(self.other)
        self.assertEqual(self._advance().status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self._advance().status_code, status.HTTP_200_OK)

    def test_detail_lists_what_each_step_still_needs(self):
        resp = self.client.get(reverse("process-detail", args=[self.process.id]))
        missing = {s["step_number"]: s["missing"] for s in resp.data["steps"]}
        # The category comes from the header; the client papers are not uploaded yet. `land_id`
        # and the real-estate paper now belong to Step 4 (UC-037, UC-041).
        self.assertNotIn("land_id", missing[1])
        self.assertNotIn("category", missing[1])
        self.assertIn("doc:ClientID", missing[1])
        self.assertIn("land_id", missing[4])
        self.assertIn("doc:RealEstate", missing[4])
        self.assertIn("start_date", missing[2])
        self.assertIn("institute:INST_S4_A", missing[4])


@override_settings(DOCUMENTS_ROOT=Path(tempfile.mkdtemp()))
class SpouseIdRequirementTests(APITestCase):
    """Step 1 wants a spouse ID only when there is a spouse (§3.6)."""

    def setUp(self):
        self.lawyer = User.objects.create_user("slw", password="pw12345678")
        self.category = Category.objects.create(code="S", name="S")

    def _missing_step1(self, **client_overrides):
        client_row = make_client(
            full_name="Person", pid=f"SP-{client_overrides.get('marital_status', 'single')}",
            mother_full_name="Mother", category=self.category, **client_overrides
        )
        process = create_process(
            client=client_row, assigned_lawyer=self.lawyer, actor=self.lawyer,
            category=self.category,
        )
        step1 = process.steps.get(step_number=1)
        return missing_requirements(process, 1, step1)

    def test_married_client_owes_a_spouse_id(self):
        self.assertIn("doc:SpouseID", self._missing_step1(marital_status="married"))

    def test_single_client_is_never_asked_for_a_spouse_id(self):
        self.assertNotIn("doc:SpouseID", self._missing_step1(marital_status="single"))


@override_settings(DOCUMENTS_ROOT=Path(tempfile.mkdtemp()))
class ClientChangeRecomputesStepTests(APITestCase):
    """Marital status decides whether Step 1 owes a spouse ID, so editing the client must
    re-derive the stored step status — otherwise the badge says complete while it is not."""

    def setUp(self):
        self.lawyer = User.objects.create_user("clw", password="pw12345678")
        self.category = Category.objects.create(code="R", name="R")
        self.client_row = make_client(
            full_name="Recompute", pid="RC-1", mother_full_name="Mother",
            category=self.category, created_by=self.lawyer,
        )
        self.process = create_process(
            client=self.client_row, assigned_lawyer=self.lawyer, actor=self.lawyer,
            category=self.category,
        )
        self.client.force_authenticate(self.lawyer)
        for doc_type in ("ClientID", "SignedAgreement"):
            self.client.post(
                reverse("document-list"),
                {
                    "process": self.process.id,
                    "step_number": 1,
                    "document_type": doc_type,
                    "file": SimpleUploadedFile(
                        "f.pdf", make_pdf(), content_type="application/pdf"
                    ),
                },
                format="multipart",
            )

    def test_marrying_the_client_reopens_a_completed_step_1(self):
        step1 = self.process.steps.get(step_number=1)
        self.assertEqual(step1.status, ProcessStep.Status.COMPLETE)

        resp = self.client.patch(
            reverse("client-detail", args=[self.client_row.id]),
            {
                "marital_status": "married",
                "spouse_name": "Partner",
                "spouse_date_of_birth": "1992-02-02",
                "spouse_mother_full_name": "Partner Mother",
                "version": self.client_row.version,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        step1.refresh_from_db()
        self.assertEqual(step1.status, ProcessStep.Status.IN_PROGRESS)


@override_settings(DOCUMENTS_ROOT=Path(tempfile.mkdtemp()))
class StepStartDateTests(APITestCase):
    """Proceeding into a step stamps its start date — the office was typing them (UC-050)."""

    def setUp(self):
        self.lawyer = User.objects.create_user("date_lw", password="pw12345678")
        self.category = Category.objects.create(code="A", name="A")
        self.process = create_process(
            client=make_client(pid="197712120001", category=self.category),
            assigned_lawyer=self.lawyer,
            actor=self.lawyer,
            category=self.category,
        )
        self.client.force_authenticate(self.lawyer)

    def _proceed(self):
        self.process.refresh_from_db()
        return self.client.post(
            reverse("process-advance-step", args=[self.process.id]),
            {"version": self.process.version},
            format="json",
        )

    def _step(self, n):
        return ProcessStep.objects.get(process=self.process, step_number=n)

    def test_step_1_is_started_when_the_case_is_opened(self):
        """Step 1 is never proceeded *into* — opening the case is what starts it."""
        self.assertIsNotNone(self._step(1).start_date)

    def test_proceeding_stamps_the_step_it_opens(self):
        """With no end date on the step being left, today is the fallback (UC-073)."""
        self.assertIsNone(self._step(2).start_date)
        self.assertEqual(self._proceed().status_code, status.HTTP_200_OK)
        self.assertEqual(self._step(2).start_date, timezone.now().date())

    def test_a_step_starts_where_the_previous_one_ended(self):
        """The case moves on from the institute that just finished, not from today (UC-073)."""
        finished = date(2026, 3, 9)
        step1 = self._step(1)
        step1.end_date = finished
        step1.save(update_fields=["end_date"])

        self.assertEqual(self._proceed().status_code, status.HTTP_200_OK)
        self.assertEqual(self._step(2).start_date, finished)

    def test_each_step_inherits_the_end_date_of_the_one_before_it(self):
        """Walking the whole case: every step picks up its own predecessor, not step 1's."""
        ends = {1: date(2026, 3, 9), 2: date(2026, 4, 2), 3: date(2026, 5, 20), 4: date(2026, 6, 1)}
        for n in (1, 2, 3, 4):
            step = self._step(n)
            step.end_date = ends[n]
            step.save(update_fields=["end_date"])
            self.assertEqual(self._proceed().status_code, status.HTTP_200_OK)
            self.assertEqual(self._step(n + 1).start_date, ends[n])

    def test_proceeding_does_not_overwrite_a_date_entered_by_hand(self):
        """A typed date is usually a correction — the papers went out earlier than today."""
        earlier = date(2026, 1, 5)
        step2 = self._step(2)
        step2.start_date = earlier
        step2.save(update_fields=["start_date"])

        self.assertEqual(self._proceed().status_code, status.HTTP_200_OK)
        self.assertEqual(self._step(2).start_date, earlier)

    def test_every_step_gets_a_start_date_as_the_case_walks_forward(self):
        """Steps 3, 4 and 5 had no dates at all before this, so the cover sheet printed none."""
        for _ in range(4):
            self.assertEqual(self._proceed().status_code, status.HTTP_200_OK)
        for n in (1, 2, 3, 4, 5):
            self.assertIsNotNone(self._step(n).start_date, f"step {n} has no start date")
