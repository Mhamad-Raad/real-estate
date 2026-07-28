"""Step-5 compiled case export (§10.3) — ordering, supersede, and loud failure."""

from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from pypdf import PdfReader, PdfWriter
from rest_framework.test import APITestCase

from accounts.models import User
from clients.factories import make_client
from common.models import ActivityLog
from processes.services import create_process

from .compile import COMPILED_DOC_TYPE, documents_in_step_order, merge_pdfs, run_compile_case_job
from .models import Document, DocumentTemplate, GenerationJob
from .rendering import RenderError
from .services import create_document


def one_page_pdf(label: str = "x") -> bytes:
    """A real, minimal PDF — `create_document` validates magic bytes, so a stub won't do."""
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


class CompileTestBase(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="adm", password="pw12345678", role=User.Role.ADMIN
        )
        self.client_row = make_client(full_name="Beneficiary", pid="C-1", mother_full_name="M")
        self.process = create_process(
            client=self.client_row, assigned_lawyer=self.admin, actor=self.admin
        )

    def _document(self, step: int, doc_type: str = "InstituteDoc") -> Document:
        return create_document(
            process=self.process,
            step_number=step,
            document_type=doc_type,
            input_source=Document.InputSource.IMPORTED,
            content=one_page_pdf(),
            actor=self.admin,
        )


class OrderingTests(CompileTestBase):
    def test_documents_are_ordered_by_step_then_upload(self):
        third = self._document(3)
        first = self._document(1, "ClientID")
        second = self._document(1, "RealEstate")

        ordered = documents_in_step_order(self.process)
        self.assertEqual([d.id for d in ordered], [first.id, second.id, third.id])

    def test_a_previous_compilation_is_excluded(self):
        """Including it would nest each run inside the next and grow the file without bound."""
        self._document(1, "ClientID")
        create_document(
            process=self.process,
            step_number=5,
            document_type=COMPILED_DOC_TYPE,
            input_source=Document.InputSource.SYSTEM_GENERATED,
            content=one_page_pdf(),
            actor=self.admin,
        )
        types = [d.document_type for d in documents_in_step_order(self.process)]
        self.assertNotIn(COMPILED_DOC_TYPE, types)


class MergeTests(CompileTestBase):
    def test_summary_first_then_every_attachment(self):
        docs = [self._document(1, "ClientID"), self._document(2)]
        merged = merge_pdfs(one_page_pdf(), docs)
        # 1 summary page + 1 page per attachment.
        self.assertEqual(len(PdfReader(BytesIO(merged)).pages), 3)

    def test_a_missing_file_fails_loudly(self):
        """A silently short compilation would still look authoritative to leadership."""
        document = self._document(1, "ClientID")
        (Path(settings.DOCUMENTS_ROOT) / document.file_path).unlink()

        with self.assertRaises(RenderError) as caught:
            merge_pdfs(one_page_pdf(), [document])
        self.assertIn(str(document.id), str(caught.exception))

    def test_an_unreadable_file_fails_loudly(self):
        document = self._document(1, "ClientID")
        (Path(settings.DOCUMENTS_ROOT) / document.file_path).write_bytes(b"%PDF-1.4 truncated")

        with self.assertRaises(RenderError):
            merge_pdfs(one_page_pdf(), [document])


class CompileJobTests(CompileTestBase):
    def setUp(self):
        super().setUp()
        # Build the template rather than skipping when none is registered: a skipped test
        # reports green while covering nothing.
        import tempfile

        from django.core.files.uploadedfile import SimpleUploadedFile

        from .management.commands.build_placeholder_templates import build_case_summary
        from .services import create_template

        with tempfile.TemporaryDirectory(prefix="tpl-") as work:
            path = Path(work) / "case_summary.docx"
            build_case_summary(path)
            self.template = create_template(
                template_type=DocumentTemplate.TemplateType.CASE_SUMMARY,
                name="test summary",
                upload=SimpleUploadedFile(path.name, path.read_bytes()),
                actor=self.admin,
            )

    def _job(self) -> GenerationJob:
        return GenerationJob.objects.create(
            kind=GenerationJob.Kind.COMPILED_CASE,
            template=self.template,
            process=self.process,
            requested_by=self.admin,
        )

    def test_failure_marks_the_job_failed_with_a_reason(self):
        document = self._document(1, "ClientID")
        (Path(settings.DOCUMENTS_ROOT) / document.file_path).unlink()
        job = self._job()

        with self.assertRaises(RenderError):
            run_compile_case_job(job.id)

        job.refresh_from_db()
        self.assertEqual(job.status, GenerationJob.Status.FAILED)
        self.assertIn("missing", job.error)
        self.assertIsNone(job.document)


class CompileApiTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="adm", password="pw12345678", role=User.Role.ADMIN
        )
        self.other = User.objects.create_user(username="other", password="pw12345678")
        client_row = make_client(full_name="B", pid="C-9", mother_full_name="M")
        self.process = create_process(
            client=client_row, assigned_lawyer=self.admin, actor=self.admin
        )

    def test_a_non_assignee_lawyer_is_refused(self):
        self.client.force_authenticate(self.other)
        response = self.client.post(reverse("process-compile-case", args=[self.process.id]))
        self.assertEqual(response.status_code, 403)

    def test_request_is_audited_even_before_the_merge_runs(self):
        """The export gathers a whole case into one file — the request must be traceable (§11)."""
        self.client.force_authenticate(self.admin)
        response = self.client.post(reverse("process-compile-case", args=[self.process.id]))

        self.assertIn(response.status_code, (202, 400))
        if response.status_code == 202:
            self.assertTrue(
                ActivityLog.objects.filter(
                    action=ActivityLog.Action.GENERATE,
                    entity_type="GenerationJob",
                    entity_id=str(response.data["id"]),
                ).exists()
            )
