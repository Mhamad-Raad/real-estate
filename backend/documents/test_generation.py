"""Letter generation: context contract, job outcomes, and the endpoints around them (§6.6, §6.8)."""

import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from catalog.models import Category
from catalog.document_types import ELIGIBILITY_LETTER
from clients.factories import make_client
from common.models import ActivityLog
from processes.services import create_process

from .generation import (
    run_eligibility_job,
    run_process_list_job,
    start_eligibility_job,
    start_process_list_job,
)
from .letters import eligibility_context, process_list_context, to_arabic_indic
from .management.commands.build_placeholder_templates import (
    build_eligibility_single,
    build_process_list,
)
from .factories import HAS_LIBREOFFICE, NO_LIBREOFFICE_REASON
from .models import Document, DocumentTemplate, GenerationJob



def make_template(template_type, builder, name="T") -> DocumentTemplate:
    """Register a placeholder template the same way an admin upload would."""
    from .services import create_template

    with tempfile.TemporaryDirectory(prefix="tpl-test-") as work:
        path = Path(work) / "t.docx"
        builder(path)
        return create_template(
            template_type=template_type,
            name=name,
            upload=SimpleUploadedFile("t.docx", path.read_bytes()),
            actor=None,
        )


class LetterContextTests(TestCase):
    """The context dict is the contract the .docx binds to — the office's own file uses it too."""

    def setUp(self):
        self.category = Category.objects.create(code="L", name="L")
        self.lawyer = User.objects.create_user("ctx", password="pw12345678")

    def _process(self, **client_overrides):
        client_row = make_client(
            pid=f"CTX-{client_overrides.get('marital_status', 'single')}",
            category=self.category,
            **client_overrides,
        )
        return create_process(
            client=client_row, assigned_lawyer=self.lawyer, actor=self.lawyer,
            category=self.category,
        )

    def test_digits_are_arabic_indic_and_conversion_is_idempotent(self):
        self.assertEqual(to_arabic_indic(1990), "١٩٩٠")
        self.assertEqual(to_arabic_indic("١٩٩٠"), "١٩٩٠")

    def test_married_beneficiary_fills_the_spouse_columns(self):
        process = self._process(
            marital_status="married",
            spouse_name="Partner",
            spouse_date_of_birth=date(1992, 2, 2),
            spouse_mother_full_name="Partner Mother",
        )

        row = eligibility_context(process)["rows"][0]

        self.assertEqual(row["spouse_name"], "Partner")
        self.assertEqual(row["spouse_year"], "١٩٩٢")
        self.assertEqual(row["spouse_mother_name"], "Partner Mother")
        self.assertEqual(row["year"], "١٩٩٠")
        self.assertEqual(row["n"], "١")

    def test_unmarried_beneficiary_leaves_the_spouse_columns_blank(self):
        """The paper form keeps the spouse cells present but empty — it never drops them."""
        row = eligibility_context(self._process())["rows"][0]

        self.assertEqual(row["spouse_name"], "")
        self.assertEqual(row["spouse_year"], "")
        self.assertEqual(row["spouse_mother_name"], "")

    def test_list_context_numbers_rows_and_names_its_range(self):
        first = self._process()
        last = self._process(marital_status="married")

        context = process_list_context([first, last])

        self.assertEqual([r["n"] for r in context["rows"]], ["١", "٢"])
        self.assertEqual(context["count"], "٢")
        # The letter body says which names the attached list begins and ends with.
        self.assertEqual(context["first_name"], first.client.full_name)
        self.assertEqual(context["last_name"], last.client.full_name)


@unittest.skipUnless(HAS_LIBREOFFICE, NO_LIBREOFFICE_REASON)
@override_settings(
    DOCUMENTS_ROOT=Path(tempfile.mkdtemp()), LETTER_TEMPLATES_ROOT=Path(tempfile.mkdtemp())
)
class GenerationJobTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user("gadm", password="pw12345678", role=User.Role.ADMIN)
        self.lawyer = User.objects.create_user("glw", password="pw12345678")
        self.category = Category.objects.create(code="G", name="G")
        self.client_row = make_client(pid="GEN-1", category=self.category)
        self.process = create_process(
            client=self.client_row, assigned_lawyer=self.lawyer, actor=self.lawyer,
            category=self.category,
        )

    def _run_eligibility(self, template):
        job = GenerationJob.objects.create(
            kind=GenerationJob.Kind.ELIGIBILITY, template=template,
            process=self.process, requested_by=self.lawyer,
        )
        run_eligibility_job(job.id)
        job.refresh_from_db()
        return job

    def test_eligibility_job_produces_a_downloadable_file_and_files_nothing_on_the_case(self):
        """UC-075: the office prints this letter; it is not archived on the allocation.

        Filing it also put it in the Step-5 compilation, which is where they noticed it.
        """
        template = make_template(
            DocumentTemplate.TemplateType.ELIGIBILITY_SINGLE, build_eligibility_single
        )

        job = self._run_eligibility(template)

        self.assertEqual(job.status, GenerationJob.Status.DONE)
        self.assertTrue((settings.GENERATED_ROOT / job.output_path).is_file())
        # Nothing on the case, so nothing for the compiled export to pick up either.
        self.assertIsNone(job.document)
        self.assertFalse(
            Document.all_objects.filter(
                process=self.process, document_type=ELIGIBILITY_LETTER
            ).exists()
        )
        # It lives outside the beneficiary's folder, like the other unfiled outputs (§6.8).
        self.assertTrue(job.output_path.startswith("letters/"))

    def test_letters_from_other_cases_are_swept_once_they_expire(self):
        """UC-075: nothing on a case points at a letter file, so without this the store would grow
        by one permanent PDF per case ever generated — the very thing unfiling it was meant to
        avoid. Swept on generation rather than on a schedule: the office computers are off when
        beat fires, so a nightly sweep would never run once."""
        template = make_template(
            DocumentTemplate.TemplateType.ELIGIBILITY_SINGLE, build_eligibility_single
        )
        other = create_process(
            client=make_client(pid="GEN-OLD", category=self.category),
            assigned_lawyer=self.lawyer, actor=self.lawyer, category=self.category,
        )
        stale_job = GenerationJob.objects.create(
            kind=GenerationJob.Kind.ELIGIBILITY, template=template,
            process=other, requested_by=self.lawyer,
        )
        run_eligibility_job(stale_job.id)
        stale_job.refresh_from_db()
        stale_path = settings.GENERATED_ROOT / stale_job.output_path
        self.assertTrue(stale_path.is_file())
        # Age it past the window. `created_at` is auto_now_add, so the ORM cannot set it directly.
        GenerationJob.objects.filter(pk=stale_job.pk).update(
            created_at=timezone.now()
            - timedelta(days=settings.GENERATED_OUTPUT_RETENTION_DAYS + 1)
        )

        fresh = self._run_eligibility(template)

        self.assertFalse(stale_path.exists(), "an expired letter from another case was kept")
        self.assertTrue((settings.GENERATED_ROOT / fresh.output_path).is_file())

    def test_a_recent_letter_on_another_case_is_left_alone(self):
        """The sweep must not delete a letter a colleague is printing at the next desk."""
        template = make_template(
            DocumentTemplate.TemplateType.ELIGIBILITY_SINGLE, build_eligibility_single
        )
        other = create_process(
            client=make_client(pid="GEN-NEW", category=self.category),
            assigned_lawyer=self.lawyer, actor=self.lawyer, category=self.category,
        )
        theirs = GenerationJob.objects.create(
            kind=GenerationJob.Kind.ELIGIBILITY, template=template,
            process=other, requested_by=self.lawyer,
        )
        run_eligibility_job(theirs.id)
        theirs.refresh_from_db()

        self._run_eligibility(template)

        self.assertTrue((settings.GENERATED_ROOT / theirs.output_path).is_file())

    def test_regenerating_replaces_the_previous_letter_file(self):
        """Nothing on the case points at these, so each run must clear the last one's file."""
        template = make_template(
            DocumentTemplate.TemplateType.ELIGIBILITY_SINGLE, build_eligibility_single
        )

        first = self._run_eligibility(template)
        first_path = settings.GENERATED_ROOT / first.output_path
        second = self._run_eligibility(template)

        self.assertNotEqual(first.output_path, second.output_path)
        self.assertFalse(first_path.exists(), "the superseded letter was left on disk")
        self.assertTrue((settings.GENERATED_ROOT / second.output_path).is_file())
        # The job rows both survive — they are the record of who generated what (§11).
        self.assertEqual(
            GenerationJob.objects.filter(
                kind=GenerationJob.Kind.ELIGIBILITY, process=self.process
            ).count(),
            2,
        )

    def test_list_job_writes_a_standalone_file_outside_any_person_folder(self):
        template = make_template(DocumentTemplate.TemplateType.PROCESS_LIST, build_process_list)
        job = GenerationJob.objects.create(
            kind=GenerationJob.Kind.PROCESS_LIST, template=template,
            process_ids=[self.process.id], requested_by=self.lawyer,
        )

        run_process_list_job(job.id)

        job.refresh_from_db()
        self.assertEqual(job.status, GenerationJob.Status.DONE)
        self.assertTrue(job.output_path.startswith("lists/"))
        self.assertTrue((settings.GENERATED_ROOT / job.output_path).is_file())
        # It spans people, so it is not a Document on anyone's process (§6.8).
        self.assertFalse(Document.objects.filter(process=self.process).exists())

    def test_an_expired_list_is_swept_when_the_next_one_is_generated(self):
        """UC-096: the lists directory grew by one permanent PDF per generation, for ever — the
        sweep was letters-only, so the office found the folder full of files nothing points at."""
        template = make_template(DocumentTemplate.TemplateType.PROCESS_LIST, build_process_list)
        stale_job = GenerationJob.objects.create(
            kind=GenerationJob.Kind.PROCESS_LIST, template=template,
            process_ids=[self.process.id], requested_by=self.lawyer,
        )
        run_process_list_job(stale_job.id)
        stale_job.refresh_from_db()
        stale_path = settings.GENERATED_ROOT / stale_job.output_path
        self.assertTrue(stale_path.is_file())
        GenerationJob.objects.filter(pk=stale_job.pk).update(
            created_at=timezone.now()
            - timedelta(days=settings.GENERATED_OUTPUT_RETENTION_DAYS + 1)
        )

        fresh = GenerationJob.objects.create(
            kind=GenerationJob.Kind.PROCESS_LIST, template=template,
            process_ids=[self.process.id], requested_by=self.lawyer,
        )
        run_process_list_job(fresh.id)
        fresh.refresh_from_db()

        self.assertFalse(stale_path.exists(), "an expired list letter was kept for ever")
        self.assertTrue((settings.GENERATED_ROOT / fresh.output_path).is_file())

    def test_a_recent_list_is_left_alone(self):
        """A list has no per-case predecessor to supersede, so only age may retire one — the
        colleague printing this morning's list must not lose it to this afternoon's."""
        template = make_template(DocumentTemplate.TemplateType.PROCESS_LIST, build_process_list)
        theirs = GenerationJob.objects.create(
            kind=GenerationJob.Kind.PROCESS_LIST, template=template,
            process_ids=[self.process.id], requested_by=self.lawyer,
        )
        run_process_list_job(theirs.id)
        theirs.refresh_from_db()
        theirs_path = settings.GENERATED_ROOT / theirs.output_path

        mine = GenerationJob.objects.create(
            kind=GenerationJob.Kind.PROCESS_LIST, template=template,
            process_ids=[self.process.id], requested_by=self.lawyer,
        )
        run_process_list_job(mine.id)

        self.assertTrue(theirs_path.is_file(), "a list generated minutes ago was swept")

    def test_a_failed_render_marks_the_job_failed_with_its_reason(self):
        template = make_template(
            DocumentTemplate.TemplateType.ELIGIBILITY_SINGLE, build_eligibility_single
        )
        (settings.LETTER_TEMPLATES_ROOT / template.file_path).unlink()
        job = GenerationJob.objects.create(
            kind=GenerationJob.Kind.ELIGIBILITY, template=template,
            process=self.process, requested_by=self.lawyer,
        )

        with self.assertRaises(Exception):
            run_eligibility_job(job.id)

        job.refresh_from_db()
        self.assertEqual(job.status, GenerationJob.Status.FAILED)
        self.assertIn("missing", job.error.lower())
        self.assertIsNone(job.document)


@override_settings(LETTER_TEMPLATES_ROOT=Path(tempfile.mkdtemp()))
class GenerationApiTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user("aadm", password="pw12345678", role=User.Role.ADMIN)
        self.lawyer = User.objects.create_user("alw", password="pw12345678")
        self.other = User.objects.create_user("oth", password="pw12345678")
        self.category = Category.objects.create(code="A", name="A")
        self.process = create_process(
            client=make_client(pid="API-1", category=self.category),
            assigned_lawyer=self.lawyer, actor=self.lawyer, category=self.category,
        )

    def test_generating_without_an_uploaded_template_is_a_clear_400(self):
        self.client.force_authenticate(self.lawyer)

        resp = self.client.post(
            reverse("process-generate-eligibility", args=[self.process.id]), {}, format="json"
        )

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("template", resp.data)

    def test_only_the_assignee_or_an_admin_may_generate_a_letter(self):
        make_template(
            DocumentTemplate.TemplateType.ELIGIBILITY_SINGLE, build_eligibility_single
        )
        self.client.force_authenticate(self.other)

        resp = self.client.post(
            reverse("process-generate-eligibility", args=[self.process.id]), {}, format="json"
        )

        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_assignee_queues_a_job(self):
        make_template(
            DocumentTemplate.TemplateType.ELIGIBILITY_SINGLE, build_eligibility_single
        )
        self.client.force_authenticate(self.lawyer)

        resp = self.client.post(
            reverse("process-generate-eligibility", args=[self.process.id]), {}, format="json"
        )

        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(resp.data["status"], GenerationJob.Status.PENDING)

    def test_bulk_generation_rejects_ids_that_do_not_exist(self):
        """The ids come from the browser, so the server re-checks every one of them (§6.8)."""
        make_template(DocumentTemplate.TemplateType.PROCESS_LIST, build_process_list)
        self.client.force_authenticate(self.other)

        resp = self.client.post(
            reverse("process-generate-document"),
            {"process_ids": [self.process.id, 999999]},
            format="json",
        )

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("process_ids", resp.data)

    def test_any_authenticated_user_may_generate_a_list_of_rows_they_can_see(self):
        make_template(DocumentTemplate.TemplateType.PROCESS_LIST, build_process_list)
        second = create_process(
            client=make_client(full_name="Second", pid="199001019999"),
            assigned_lawyer=self.lawyer,
            actor=self.lawyer,
        )
        self.client.force_authenticate(self.other)

        # Two rows: still the list letter, still open to anyone — it only *exports* (§6.8).
        resp = self.client.post(
            reverse("process-generate-document"),
            {"process_ids": [self.process.id, second.id]},
            format="json",
        )

        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(resp.data["kind"], GenerationJob.Kind.PROCESS_LIST)

    def test_one_selected_case_produces_that_persons_own_letter(self):
        """UC-016: selecting a single case used to yield a one-row *list* letter."""
        make_template(
            DocumentTemplate.TemplateType.ELIGIBILITY_SINGLE, build_eligibility_single
        )
        self.client.force_authenticate(self.lawyer)

        resp = self.client.post(
            reverse("process-generate-document"),
            {"process_ids": [self.process.id]},
            format="json",
        )

        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(resp.data["kind"], GenerationJob.Kind.ELIGIBILITY)

    def test_a_non_assignee_cannot_file_a_single_letter_onto_someone_elses_case(self):
        """This branch WRITES a Document, so it follows the case's assignment — not the export rule."""
        make_template(
            DocumentTemplate.TemplateType.ELIGIBILITY_SINGLE, build_eligibility_single
        )
        self.client.force_authenticate(self.other)

        resp = self.client.post(
            reverse("process-generate-document"),
            {"process_ids": [self.process.id]},
            format="json",
        )

        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_a_job_is_visible_only_to_its_requester_or_an_admin(self):
        make_template(DocumentTemplate.TemplateType.PROCESS_LIST, build_process_list)
        job = start_process_list_job(process_ids=[self.process.id], actor=self.lawyer)

        self.client.force_authenticate(self.other)
        self.assertEqual(
            self.client.get(reverse("generation-job-detail", args=[job.id])).status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.client.force_authenticate(self.admin)
        self.assertEqual(
            self.client.get(reverse("generation-job-detail", args=[job.id])).status_code,
            status.HTTP_200_OK,
        )


@override_settings(LETTER_TEMPLATES_ROOT=Path(tempfile.mkdtemp()))
class DocumentTemplateApiTests(APITestCase):
    """Templates are read-only over the API (§6.6, UC-010) — installed from the repo, not uploaded."""

    def setUp(self):
        self.admin = User.objects.create_user("tadm", password="pw12345678", role=User.Role.ADMIN)
        self.lawyer = User.objects.create_user("tlw", password="pw12345678")

    def _docx_bytes(self) -> bytes:
        with tempfile.TemporaryDirectory(prefix="tpl-api-") as work:
            path = Path(work) / "t.docx"
            build_eligibility_single(path)
            return path.read_bytes()

    def test_even_an_admin_cannot_upload_a_template(self):
        """The boundary moved, not just the buttons — hiding the UI is never the boundary (§7.2)."""
        self.client.force_authenticate(self.admin)

        resp = self.client.post(
            reverse("document-template-list"),
            {
                "template_type": DocumentTemplate.TemplateType.ELIGIBILITY_SINGLE,
                "name": "Letter",
                "file": SimpleUploadedFile("t.docx", self._docx_bytes()),
            },
            format="multipart",
        )

        self.assertEqual(resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_an_admin_cannot_edit_or_delete_a_template(self):
        template = make_template(
            DocumentTemplate.TemplateType.ELIGIBILITY_SINGLE, build_eligibility_single
        )
        self.client.force_authenticate(self.admin)
        url = reverse("document-template-detail", args=[template.id])

        self.assertEqual(
            self.client.patch(url, {"name": "x"}, format="json").status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )
        self.assertEqual(
            self.client.delete(url).status_code, status.HTTP_405_METHOD_NOT_ALLOWED
        )

    def test_anyone_authenticated_may_still_read_them(self):
        make_template(DocumentTemplate.TemplateType.ELIGIBILITY_SINGLE, build_eligibility_single)
        self.client.force_authenticate(self.lawyer)

        resp = self.client.get(reverse("document-template-list"))

        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_the_type_vocabulary_covers_every_backend_type(self):
        """UC-008: the frontend kept its own copy and fell a whole type behind."""
        self.client.force_authenticate(self.lawyer)

        resp = self.client.get(reverse("template-types"))

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(
            {row["code"] for row in resp.data},
            set(DocumentTemplate.TemplateType.values),
        )

@unittest.skipUnless(HAS_LIBREOFFICE, NO_LIBREOFFICE_REASON)
@override_settings(
    DOCUMENTS_ROOT=Path(tempfile.mkdtemp()), LETTER_TEMPLATES_ROOT=Path(tempfile.mkdtemp())
)
class GenerationAuditTests(APITestCase):
    """Audit is the append-only record (§11): every generation and every supersede leaves a row."""

    def setUp(self):
        self.lawyer = User.objects.create_user("audlw", password="pw12345678")
        self.category = Category.objects.create(code="U", name="U")
        self.process = create_process(
            client=make_client(pid="AUD-1", category=self.category),
            assigned_lawyer=self.lawyer, actor=self.lawyer, category=self.category,
        )

    def test_every_letter_run_is_traceable_even_though_nothing_is_filed(self):
        """The letter no longer becomes a Document (UC-075), which removed the create/delete rows
        that used to record it. The request row is therefore the *only* trace left of who produced
        a beneficiary's letter and when — so each run must have one."""
        make_template(DocumentTemplate.TemplateType.ELIGIBILITY_SINGLE, build_eligibility_single)

        first = start_eligibility_job(process=self.process, actor=self.lawyer)
        second = start_eligibility_job(process=self.process, actor=self.lawyer)

        for job in (first, second):
            self.assertTrue(
                ActivityLog.objects.filter(
                    entity_type="GenerationJob",
                    entity_id=str(job.id),
                    action=ActivityLog.Action.GENERATE,
                    actor=self.lawyer,
                ).exists(),
                f"job {job.id} left no audit row",
            )

    def test_a_failed_bulk_export_is_still_traceable(self):
        """The request is what must be recorded — a render can fail long after the click."""
        template = make_template(DocumentTemplate.TemplateType.PROCESS_LIST, build_process_list)
        job = start_process_list_job(process_ids=[self.process.id], actor=self.lawyer)
        (settings.LETTER_TEMPLATES_ROOT / template.file_path).unlink()

        with self.assertRaises(Exception):
            run_process_list_job(job.id)

        job.refresh_from_db()
        self.assertEqual(job.status, GenerationJob.Status.FAILED)
        row = ActivityLog.objects.get(
            entity_type="GenerationJob", entity_id=str(job.id), action=ActivityLog.Action.GENERATE
        )
        self.assertEqual(row.after["process_ids"], [self.process.id])


@override_settings(LETTER_TEMPLATES_ROOT=Path(tempfile.mkdtemp()))
class TemplateInstallTests(APITestCase):
    """`install_templates` is the supported install path now the API is read-only (§6.6, UC-010)."""

    def setUp(self):
        self.admin = User.objects.create_user("acadm", password="pw12345678", role=User.Role.ADMIN)

    def test_installing_retires_the_previous_active_template(self):
        """Exactly one template per type may be active, or generation could not choose."""
        first = make_template(
            DocumentTemplate.TemplateType.ELIGIBILITY_SINGLE, build_eligibility_single, name="A"
        )

        second = make_template(
            DocumentTemplate.TemplateType.ELIGIBILITY_SINGLE, build_eligibility_single, name="B"
        )

        first.refresh_from_db()
        second.refresh_from_db()
        self.assertFalse(first.is_active)
        self.assertTrue(second.is_active)

    def test_a_retired_template_is_kept_not_deleted(self):
        """A regenerated letter must stay traceable to the exact file that produced the earlier one."""
        first = make_template(
            DocumentTemplate.TemplateType.ELIGIBILITY_SINGLE, build_eligibility_single, name="A"
        )
        make_template(
            DocumentTemplate.TemplateType.ELIGIBILITY_SINGLE, build_eligibility_single, name="B"
        )

        first.refresh_from_db()
        self.assertFalse(first.is_deleted)

    def test_the_command_skips_a_file_that_is_already_installed_unchanged(self):
        """Reinstalling an identical file would churn the history for no change at all."""
        from io import StringIO

        from django.core.management import call_command

        out = StringIO()
        call_command("install_templates", stdout=out)
        first_pass = DocumentTemplate.objects.count()

        out2 = StringIO()
        call_command("install_templates", stdout=out2)

        self.assertEqual(DocumentTemplate.objects.count(), first_pass)
