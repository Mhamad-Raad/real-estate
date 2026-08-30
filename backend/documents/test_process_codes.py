"""The office's code list (§6.8, UC-057) — its own template, its own step gate."""

from unittest.mock import patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from catalog.models import Category
from clients.factories import make_client
from processes.models import Process
from processes.services import create_process

from .letters import process_codes_context
from .models import DocumentTemplate, GenerationJob


class ProcessCodesContextTests(APITestCase):
    def test_the_row_carries_number_name_code_and_land(self):
        category = Category.objects.create(code="A", name="A")
        lawyer = User.objects.create_user("ctx_lw", password="pw12345678")
        process = create_process(
            client=make_client(full_name="Person One", pid="199001010301", category=category),
            assigned_lawyer=lawyer, actor=lawyer, category=category,
        )
        process.land_id = "LND-1"
        process.save(update_fields=["land_id"])

        rows = process_codes_context([process])["rows"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["full_name"], "Person One")
        self.assertEqual(rows[0]["code"], process.unique_code)
        self.assertEqual(rows[0]["land_id"], "LND-1")
        # The office's forms are printed in Arabic-Indic digits (§6.6), the row number included.
        self.assertEqual(rows[0]["n"], "١")


class ProcessCodesApiTests(APITestCase):
    def setUp(self):
        self.lawyer = User.objects.create_user("codes_lw", password="pw12345678")
        self.category = Category.objects.create(code="A", name="A")
        DocumentTemplate.objects.create(
            template_type=DocumentTemplate.TemplateType.PROCESS_CODES,
            name="codes", file_path="x.docx", sha256="s", is_active=True,
        )
        self.client.force_authenticate(self.lawyer)

    def _case(self, pid, step):
        process = create_process(
            client=make_client(pid=pid, category=self.category),
            assigned_lawyer=self.lawyer, actor=self.lawyer, category=self.category,
        )
        Process.objects.filter(pk=process.pk).update(current_step=step)
        return process

    def _post(self, ids):
        with patch("documents.tasks.generate_process_codes.delay"):
            return self.client.post(
                reverse("process-generate-codes"), {"process_ids": ids}, format="json"
            )

    def test_a_case_that_reached_step_3_can_be_printed(self):
        resp = self._post([self._case("199001010302", 3).id])
        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED)
        job = GenerationJob.objects.get(pk=resp.data["id"])
        self.assertEqual(job.kind, GenerationJob.Kind.PROCESS_CODES)

    def test_an_earlier_case_is_refused_by_the_server(self):
        """The button hides it, but UI hiding is never the boundary (§7.2)."""
        early = self._case("199001010303", 2)
        resp = self._post([early.id])
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("process_ids", resp.data)
        self.assertFalse(GenerationJob.objects.filter(kind="process_codes").exists())

    def test_one_early_case_refuses_the_whole_request(self):
        ok, early = self._case("199001010304", 4), self._case("199001010305", 1)
        self.assertEqual(self._post([ok.id, early.id]).status_code, status.HTTP_400_BAD_REQUEST)

    def test_an_unknown_id_is_a_400_not_a_500(self):
        self.assertEqual(self._post([999999]).status_code, status.HTTP_400_BAD_REQUEST)

    def test_the_request_is_audited_before_anything_renders(self):
        """A bulk export of personal data must be traceable from the moment it is asked for (§11)."""
        from common.models import ActivityLog

        self._post([self._case("199001010306", 5).id])
        self.assertTrue(
            ActivityLog.objects.filter(entity_type="GenerationJob").exists(),
            "the code-list request left no audit row",
        )


class ConcludedByTests(APITestCase):
    """The compiled export names whoever closed the case (UC-044)."""

    def setUp(self):
        self.admin = User.objects.create_user("cb_adm", password="pw12345678", role=User.Role.ADMIN)
        self.category = Category.objects.create(code="A", name="A")
        self.process = create_process(
            client=make_client(pid="199505050401", category=self.category),
            assigned_lawyer=self.admin, actor=self.admin, category=self.category,
        )
        self.client.force_authenticate(self.admin)

    def _summary(self):
        from .summary import case_summary_context
        from processes.models import Process as P
        p = P.objects.prefetch_related("steps", "institute_entries", "documents").get(pk=self.process.pk)
        return case_summary_context(p, [])

    def test_an_open_case_names_nobody(self):
        """An export taken mid-flight must not claim somebody concluded work that is still open."""
        self.assertEqual(self._summary()["concluded_by"], "")

    def test_completing_the_case_records_who_did_it(self):
        self.process.refresh_from_db()
        resp = self.client.post(
            reverse("process-complete", args=[self.process.id]),
            {"force": True, "version": self.process.version}, format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.process.refresh_from_db()
        self.assertEqual(self.process.completed_by, self.admin)
        self.assertEqual(self._summary()["concluded_by"], "cb_adm")

    def test_a_later_re_completion_does_not_rewrite_the_name(self):
        """The first person to close it is the one already named on the paperwork that went out."""
        self.process.refresh_from_db()
        self.client.post(
            reverse("process-complete", args=[self.process.id]),
            {"force": True, "version": self.process.version}, format="json",
        )
        other = User.objects.create_user("cb_other", password="pw12345678", role=User.Role.ADMIN)
        self.client.force_authenticate(other)
        self.process.refresh_from_db()
        self.client.post(
            reverse("process-complete", args=[self.process.id]),
            {"force": True, "version": self.process.version}, format="json",
        )
        self.process.refresh_from_db()
        self.assertEqual(self.process.completed_by, self.admin)
