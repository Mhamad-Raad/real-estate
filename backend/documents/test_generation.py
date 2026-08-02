"""Letter generation: context contract, job outcomes, and the endpoints around them (§6.6, §6.8)."""

import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from catalog.models import Category
from clients.factories import make_client
from common.models import ActivityLog
from processes.services import create_process

from .generation import (
    ELIGIBILITY_DOC_TYPE,
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
from .models import Document, DocumentTemplate, GenerationJob

HAS_LIBREOFFICE = shutil.which(settings.LIBREOFFICE_BIN) is not None


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


@unittest.skipUnless(HAS_LIBREOFFICE, "LibreOffice not installed (run inside the container)")
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

    def test_eligibility_job_attaches_a_generated_document_and_audits_it(self):
        template = make_template(
            DocumentTemplate.TemplateType.ELIGIBILITY_SINGLE, build_eligibility_single
        )
        job = GenerationJob.objects.create(
            kind=GenerationJob.Kind.ELIGIBILITY, template=template,
            process=self.process, requested_by=self.lawyer,
        )

        run_eligibility_job(job.id)

        job.refresh_from_db()
        self.assertEqual(job.status, GenerationJob.Status.DONE)
        document = job.document
        self.assertEqual(document.document_type, ELIGIBILITY_DOC_TYPE)
        self.assertEqual(document.input_source, Document.InputSource.SYSTEM_GENERATED)
        self.assertTrue((settings.DOCUMENTS_ROOT / document.file_path).is_file())
        # The job itself is audited when it is REQUESTED (see GenerationAuditTests); here the
        # artefact is what matters — the stored document carries its own create row.
        self.assertTrue(
            ActivityLog.objects.filter(
                entity_type="Document",
                entity_id=str(document.id),
                action=ActivityLog.Action.CREATE,
            ).exists()
        )

    def test_regenerating_supersedes_the_previous_letter_instead_of_overwriting_it(self):
        """The earlier PDF stays on disk, soft-deleted — the audit trail keeps what was sent."""
        template = make_template(
            DocumentTemplate.TemplateType.ELIGIBILITY_SINGLE, build_eligibility_single
        )

        def generate():
            job = GenerationJob.objects.create(
                kind=GenerationJob.Kind.ELIGIBILITY, template=template,
                process=self.process, requested_by=self.lawyer,
            )
            run_eligibility_job(job.id)
            job.refresh_from_db()
            return job.document

        first = generate()
        second = generate()

        self.assertNotEqual(first.id, second.id)
        first.refresh_from_db()
        self.assertTrue(first.is_deleted)
        self.assertFalse(second.is_deleted)
        # Exactly one live letter, so Step 1 never shows two.
        live = Document.objects.filter(process=self.process, document_type=ELIGIBILITY_DOC_TYPE)
        self.assertEqual(live.count(), 1)

    def test_list_job_writes_a_standalone_file_outside_any_person_folder(self):
        template = make_template(DocumentTemplate.TemplateType.PROCESS_LIST, build_process_list)
        job = GenerationJob.objects.create(
            kind=GenerationJob.Kind.PROCESS_LIST, template=template,
            process_ids=[self.process.id], requested_by=self.lawyer,
        )

        run_process_list_job(job.id)

        job.refresh_from_db()
        self.assertEqual(job.status, GenerationJob.Status.DONE)
        self.assertTrue(job.output_path.startswith("_generated/lists/"))
        self.assertTrue((settings.DOCUMENTS_ROOT / job.output_path).is_file())
        # It spans people, so it is not a Document on anyone's process (§6.8).
        self.assertFalse(Document.objects.filter(process=self.process).exists())

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
    def setUp(self):
        self.admin = User.objects.create_user("tadm", password="pw12345678", role=User.Role.ADMIN)
        self.lawyer = User.objects.create_user("tlw", password="pw12345678")

    def _docx_bytes(self) -> bytes:
        with tempfile.TemporaryDirectory(prefix="tpl-api-") as work:
            path = Path(work) / "t.docx"
            build_eligibility_single(path)
            return path.read_bytes()

    def _upload(self, content=None, name="Letter"):
        return self.client.post(
            reverse("document-template-list"),
            {
                "template_type": DocumentTemplate.TemplateType.ELIGIBILITY_SINGLE,
                "name": name,
                "file": SimpleUploadedFile("t.docx", content or self._docx_bytes()),
            },
            format="multipart",
        )

    def test_a_lawyer_cannot_upload_a_template(self):
        self.client.force_authenticate(self.lawyer)

        self.assertEqual(self._upload().status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_upload_becomes_the_active_template(self):
        self.client.force_authenticate(self.admin)

        resp = self._upload()

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(resp.data["is_active"])

    def test_a_new_upload_retires_the_previous_active_template(self):
        """Exactly one template per type may be active, or generation could not choose."""
        self.client.force_authenticate(self.admin)
        first = self._upload(name="Old").data

        second = self._upload(name="New").data

        self.assertFalse(DocumentTemplate.objects.get(pk=first["id"]).is_active)
        self.assertTrue(DocumentTemplate.objects.get(pk=second["id"]).is_active)

    def test_a_file_that_is_not_a_word_document_is_rejected(self):
        """Catching it at upload beats a generation failing hours later."""
        self.client.force_authenticate(self.admin)

        resp = self._upload(content=b"%PDF-1.4 definitely not a docx")

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("file", resp.data)


@unittest.skipUnless(HAS_LIBREOFFICE, "LibreOffice not installed (run inside the container)")
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

    def test_superseding_a_letter_audits_the_deletion_of_the_old_one(self):
        """A bulk UPDATE would soft-delete the old PDF leaving no trace of who or when."""
        template = make_template(
            DocumentTemplate.TemplateType.ELIGIBILITY_SINGLE, build_eligibility_single
        )

        def generate():
            job = GenerationJob.objects.create(
                kind=GenerationJob.Kind.ELIGIBILITY, template=template,
                process=self.process, requested_by=self.lawyer,
            )
            run_eligibility_job(job.id)
            job.refresh_from_db()
            return job

        first = generate()
        generate()

        self.assertTrue(
            ActivityLog.objects.filter(
                entity_type="Document",
                entity_id=str(first.document_id),
                action=ActivityLog.Action.DELETE,
            ).exists()
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
class TemplateActivationTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user("acadm", password="pw12345678", role=User.Role.ADMIN)
        self.client.force_authenticate(self.admin)

    def test_reactivating_a_retired_template_retires_the_current_one(self):
        """Two active templates violate the unique index; that surfaced to the client as a 500."""
        first = make_template(
            DocumentTemplate.TemplateType.ELIGIBILITY_SINGLE, build_eligibility_single, name="A"
        )
        second = make_template(
            DocumentTemplate.TemplateType.ELIGIBILITY_SINGLE, build_eligibility_single, name="B"
        )
        first.refresh_from_db()

        resp = self.client.patch(
            reverse("document-template-detail", args=[first.id]),
            {"is_active": True, "version": first.version},
            format="json",
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertTrue(first.is_active)
        self.assertFalse(second.is_active)

    def test_deleting_a_template_clears_its_active_flag(self):
        """Otherwise restoring it beside its replacement violates the one-active-per-type index."""
        active = make_template(
            DocumentTemplate.TemplateType.ELIGIBILITY_SINGLE, build_eligibility_single, name="One"
        )

        self.client.delete(reverse("document-template-detail", args=[active.id]))

        active.refresh_from_db()
        self.assertTrue(active.is_deleted)
        self.assertFalse(active.is_active)

    def test_a_restored_template_does_not_collide_with_its_replacement(self):
        active = make_template(
            DocumentTemplate.TemplateType.ELIGIBILITY_SINGLE, build_eligibility_single, name="One"
        )
        self.client.delete(reverse("document-template-detail", args=[active.id]))
        replacement = make_template(
            DocumentTemplate.TemplateType.ELIGIBILITY_SINGLE, build_eligibility_single, name="Two"
        )

        resp = self.client.post(reverse("document-template-restore", args=[active.id]))

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # Restored as retired; the replacement stays the one generation uses.
        self.assertEqual(
            DocumentTemplate.objects.filter(
                template_type=DocumentTemplate.TemplateType.ELIGIBILITY_SINGLE, is_active=True
            ).count(),
            1,
        )
        replacement.refresh_from_db()
        self.assertTrue(replacement.is_active)
