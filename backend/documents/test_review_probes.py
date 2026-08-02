"""Review probes for the It.7 batch: the generation RBAC change and the template boundary."""

import tempfile
from pathlib import Path

from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from clients.factories import make_client
from common.models import ActivityLog
from processes.services import create_process

from .management.commands.build_placeholder_templates import (
    build_eligibility_single,
    build_process_list,
)
from .models import DocumentTemplate, GenerationJob
from .test_generation import make_template


@override_settings(LETTER_TEMPLATES_ROOT=Path(tempfile.mkdtemp()))
class SingleLetterRbacTests(APITestCase):
    """UC-016 tightened this path because it now WRITES a Document (§7.2)."""

    def setUp(self):
        self.admin = User.objects.create_user("rp_adm", password="pw12345678", role=User.Role.ADMIN)
        self.lawyer = User.objects.create_user("rp_lw", password="pw12345678")
        self.other = User.objects.create_user("rp_other", password="pw12345678")
        self.process = create_process(
            client=make_client(pid="RBAC-1"), assigned_lawyer=self.lawyer, actor=self.lawyer
        )
        make_template(DocumentTemplate.TemplateType.ELIGIBILITY_SINGLE, build_eligibility_single)
        make_template(DocumentTemplate.TemplateType.PROCESS_LIST, build_process_list)

    def _post(self, ids):
        return self.client.post(
            reverse("process-generate-document"), {"process_ids": ids}, format="json"
        )

    def test_an_admin_may_file_a_single_letter_on_any_case(self):
        """The tightening must not lock admins out of a case they do not personally hold."""
        self.client.force_authenticate(self.admin)

        resp = self._post([self.process.id])

        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(resp.data["kind"], GenerationJob.Kind.ELIGIBILITY)

    def test_the_assignee_may_file_their_own(self):
        self.client.force_authenticate(self.lawyer)
        self.assertEqual(self._post([self.process.id]).status_code, status.HTTP_202_ACCEPTED)

    def test_a_non_assignee_is_refused(self):
        self.client.force_authenticate(self.other)
        self.assertEqual(self._post([self.process.id]).status_code, status.HTTP_403_FORBIDDEN)

    def test_a_non_assignee_can_still_export_a_multi_row_list(self):
        """The list letter only exports rows they can already see — that rule is unchanged."""
        second = create_process(
            client=make_client(pid="RBAC-2"), assigned_lawyer=self.lawyer, actor=self.lawyer
        )
        self.client.force_authenticate(self.other)

        resp = self._post([self.process.id, second.id])

        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(resp.data["kind"], GenerationJob.Kind.PROCESS_LIST)

    def test_a_refused_request_queues_nothing(self):
        """A 403 must not leave a job row behind for a letter that will never be filed."""
        before = GenerationJob.objects.count()
        self.client.force_authenticate(self.other)

        self._post([self.process.id])

        self.assertEqual(GenerationJob.objects.count(), before)

    def test_an_unknown_id_is_still_rejected_on_the_single_path(self):
        """The list path re-validates ids server-side; the single path must not be a way around it."""
        self.client.force_authenticate(self.admin)

        self.assertEqual(self._post([999999]).status_code, status.HTTP_404_NOT_FOUND)


@override_settings(LETTER_TEMPLATES_ROOT=Path(tempfile.mkdtemp()))
class TemplateBoundaryTests(APITestCase):
    """UC-010 swapped the viewset — check nothing the old one guaranteed was lost."""

    def setUp(self):
        self.admin = User.objects.create_user("tb_adm", password="pw12345678", role=User.Role.ADMIN)
        self.lawyer = User.objects.create_user("tb_lw", password="pw12345678")

    def test_installing_a_template_is_still_audited(self):
        """Dropping AuditedSoftDeleteViewSet must not have dropped the audit row with it."""
        template = make_template(
            DocumentTemplate.TemplateType.ELIGIBILITY_SINGLE, build_eligibility_single
        )

        self.assertTrue(
            ActivityLog.objects.filter(
                entity_type="DocumentTemplate",
                entity_id=str(template.id),
                action=ActivityLog.Action.CREATE,
            ).exists()
        )

    def test_the_restore_endpoint_is_gone(self):
        """It came from the soft-delete viewset; leaving it would be a write on a read-only API."""
        template = make_template(
            DocumentTemplate.TemplateType.ELIGIBILITY_SINGLE, build_eligibility_single
        )
        self.client.force_authenticate(self.admin)

        resp = self.client.post(f"/api/v1/document-templates/{template.id}/restore/")

        self.assertIn(resp.status_code, (status.HTTP_404_NOT_FOUND, status.HTTP_405_METHOD_NOT_ALLOWED))

    def test_reading_still_requires_authentication(self):
        """Read-only is not the same as public."""
        self.assertEqual(
            self.client.get(reverse("document-template-list")).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_the_preview_endpoint_requires_authentication(self):
        template = make_template(
            DocumentTemplate.TemplateType.ELIGIBILITY_SINGLE, build_eligibility_single
        )

        resp = self.client.get(reverse("document-template-preview", args=[template.id]))

        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_the_active_template_leads_its_type(self):
        """The screen groups by type and shows `active` first; arbitrary order made that luck."""
        for _ in range(3):
            make_template(
                DocumentTemplate.TemplateType.ELIGIBILITY_SINGLE, build_eligibility_single
            )
        self.client.force_authenticate(self.lawyer)

        rows = self.client.get(reverse("document-template-list")).data
        first = next(r for r in rows if r["template_type"] == "eligibility_single")

        self.assertTrue(first["is_active"])

    def test_every_template_is_returned_however_many_there_are(self):
        """The list feeds a *grouping*, which cannot be paged: an active row on page 2 would make
        its group render as "none installed". Retired versions are kept forever (§6.6), so the
        count only grows — past a page size this silently broke."""
        for _ in range(30):
            make_template(
                DocumentTemplate.TemplateType.PROCESS_LIST, build_process_list
            )
        self.client.force_authenticate(self.lawyer)

        rows = self.client.get(reverse("document-template-list")).data

        # A plain list, not {"results": [...]} — and all 30 of them.
        self.assertIsInstance(rows, list)
        self.assertEqual(len([r for r in rows if r["template_type"] == "process_list"]), 30)
