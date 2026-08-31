"""Step-5 compiled case export (§10.3) — ordering, supersede, and loud failure."""

import unittest
from io import BytesIO
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from pypdf import PdfReader, PdfWriter
from rest_framework.test import APITestCase

from accounts.models import User
from clients.factories import make_client
from common.models import ActivityLog
from processes.models import Process, ProcessStep
from processes.services import create_process

from .compile import COMPILED_DOC_TYPE, documents_in_step_order, merge_pdfs, run_compile_case_job
from .models import Document, DocumentTemplate, GenerationJob
from .rendering import RenderError
from .factories import HAS_LIBREOFFICE, NO_LIBREOFFICE_REASON, make_pdf
from .letters import to_arabic_indic
from .services import PayloadTooLarge, create_document
from .summary import LABELS, case_summary_context


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
            content=make_pdf(),
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
        """Including it would nest each run inside the next and grow the file without bound.
        Nothing files one any more (UC-118), but a case closed before that may still carry one."""
        self._document(1, "ClientID")
        create_document(
            process=self.process,
            step_number=5,
            document_type=COMPILED_DOC_TYPE,
            input_source=Document.InputSource.SYSTEM_GENERATED,
            content=make_pdf(),
            actor=self.admin,
        )
        types = [d.document_type for d in documents_in_step_order(self.process)]
        self.assertNotIn(COMPILED_DOC_TYPE, types)

    def test_a_scanned_case_file_is_merged(self):
        """The backlog door files the paper case as a CompiledCase (UC-114) — that scan *is* the
        case's papers, and an export that left it out would be a cover sheet and nothing else."""
        scan = self._document(5, COMPILED_DOC_TYPE)

        self.assertEqual([d.id for d in documents_in_step_order(self.process)], [scan.id])

    def test_a_letter_filed_before_the_change_is_still_left_out(self):
        """UC-075: nothing files an EligibilityLetter any more, but every case created before
        that carries one — and the office wants it out of the compilation on those too."""
        kept = self._document(1, "ClientID")
        create_document(
            process=self.process,
            step_number=1,
            document_type="EligibilityLetter",
            input_source=Document.InputSource.SYSTEM_GENERATED,
            content=make_pdf(),
            actor=self.admin,
        )

        ordered = documents_in_step_order(self.process)

        self.assertEqual([d.id for d in ordered], [kept.id])


class MergeTests(CompileTestBase):
    def test_summary_first_then_every_attachment(self):
        docs = [self._document(1, "ClientID"), self._document(2)]
        merged = merge_pdfs(make_pdf(), docs)
        # 1 summary page + 1 page per attachment.
        self.assertEqual(len(PdfReader(BytesIO(merged)).pages), 3)

    def test_a_missing_file_fails_loudly(self):
        """A silently short compilation would still look authoritative to leadership."""
        document = self._document(1, "ClientID")
        (Path(settings.DOCUMENTS_ROOT) / document.file_path).unlink()

        with self.assertRaises(RenderError) as caught:
            merge_pdfs(make_pdf(), [document])
        self.assertIn(str(document.id), str(caught.exception))

    def test_an_unreadable_file_fails_loudly(self):
        document = self._document(1, "ClientID")
        (Path(settings.DOCUMENTS_ROOT) / document.file_path).write_bytes(b"%PDF-1.4 truncated")

        with self.assertRaises(RenderError):
            merge_pdfs(make_pdf(), [document])


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

    @unittest.skipUnless(HAS_LIBREOFFICE, NO_LIBREOFFICE_REASON)
    def test_failure_marks_the_job_failed_with_a_reason(self):
        """Needs the real binary: the cover sheet renders before the merge reads the files, so
        without LibreOffice the job fails for the wrong reason and the assertion below is a lie.
        Its siblings in test_generation/test_rendering carry the same guard; this one did not, and
        left the suite red on the documented native-dev path (It.8)."""
        document = self._document(1, "ClientID")
        (Path(settings.DOCUMENTS_ROOT) / document.file_path).unlink()
        job = self._job()

        with self.assertRaises(RenderError):
            run_compile_case_job(job.id)

        job.refresh_from_db()
        self.assertEqual(job.status, GenerationJob.Status.FAILED)
        self.assertIn("missing", job.error)
        self.assertEqual(job.output_path, "")

    def _run_with_stub_cover_sheet(self, job: GenerationJob) -> None:
        # The cover sheet needs LibreOffice; what these tests hold is where the merge lands.
        with mock.patch("documents.generation.render_to_pdf", return_value=make_pdf()):
            run_compile_case_job(job.id)

    def test_the_export_is_a_one_read_job_file_not_a_document(self):
        """UC-118: nothing is filed on the case — the merge lands under GENERATED_ROOT like the
        Step-1 letter, so a closed case no longer costs twice its papers on disk."""
        self._document(1, "ClientID")
        job = self._job()

        self._run_with_stub_cover_sheet(job)

        job.refresh_from_db()
        self.assertEqual(job.status, GenerationJob.Status.DONE)
        self.assertEqual(job.output_path, f"compiled/compiled_{job.id}.pdf")
        self.assertTrue((Path(settings.GENERATED_ROOT) / job.output_path).is_file())
        self.assertFalse(
            Document.objects.filter(process=self.process, document_type=COMPILED_DOC_TYPE).exists()
        )

    def test_recompiling_removes_the_case_s_previous_export(self):
        """The largest file the app writes must not accumulate one copy per press."""
        self._document(1, "ClientID")
        first, second = self._job(), self._job()
        self._run_with_stub_cover_sheet(first)
        first.refresh_from_db()
        first_file = Path(settings.GENERATED_ROOT) / first.output_path

        self._run_with_stub_cover_sheet(second)

        self.assertFalse(first_file.is_file())
        first.refresh_from_db()
        self.assertEqual(first.output_path, f"compiled/compiled_{first.id}.pdf", "the record of what was produced stays")


class SummaryContextTests(CompileTestBase):
    def _closed_over_step_4(self):
        """A closed case with step 4 left unfinished — the shape the cover sheet names."""
        self.process.overall_status = Process.OverallStatus.COMPLETE
        self.process.save(update_fields=["overall_status"])
        ProcessStep.objects.filter(process=self.process, step_number=4).update(
            status=ProcessStep.Status.IN_PROGRESS
        )

    def test_document_count_matches_what_is_merged(self):
        """The previous compilation is still live while the summary renders — counting it would
        print a total one higher than the file actually contains."""
        self._document(1, "ClientID")
        self._document(2)
        create_document(
            process=self.process,
            step_number=5,
            document_type=COMPILED_DOC_TYPE,
            input_source=Document.InputSource.SYSTEM_GENERATED,
            content=make_pdf(),
            actor=self.admin,
        )
        attachments = documents_in_step_order(self.process)
        context = case_summary_context(self.process, attachments)

        self.assertEqual(len(attachments), 2)
        self.assertEqual(context["document_count"], to_arabic_indic(2))

    def test_a_step_the_finished_case_was_closed_over_prints_as_skipped(self):
        """UC-079: a case may complete over step 4's institutes. On a signed export "in progress"
        would read as work still outstanding, and "complete" would claim work nobody did."""
        self._closed_over_step_4()

        rows = {row["n"]: row["status"] for row in case_summary_context(self.process, [])["steps"]}

        self.assertEqual(rows[to_arabic_indic(4)], LABELS["skipped"])

    def test_the_sheet_records_what_happened_not_what_the_gate_allows_today(self):
        """UC-088: the label is deliberately **not** tied to the completion rule.

        This case has no municipality form, so today's gate would refuse to close it — yet it is
        closed, because it was closed under the previous rule or by an admin force. Re-deriving
        the label from the current policy would rewrite the cover sheet of every allocation the
        office had already signed.
        """
        self._closed_over_step_4()
        self.assertFalse(Document.objects.filter(process=self.process, step_number=4).exists())

        rows = {row["n"]: row["status"] for row in case_summary_context(self.process, [])["steps"]}

        self.assertEqual(rows[to_arabic_indic(4)], LABELS["skipped"])

    def test_an_unfinished_step_on_an_OPEN_case_still_reads_in_progress(self):
        """The relabelling is about a *closed* case — an open one is genuinely still in progress."""
        ProcessStep.objects.filter(process=self.process, step_number=4).update(
            status=ProcessStep.Status.IN_PROGRESS
        )

        rows = {row["n"]: row["status"] for row in case_summary_context(self.process, [])["steps"]}

        self.assertEqual(rows[to_arabic_indic(4)], LABELS["in_progress"])


class GeneratedSizeTests(CompileTestBase):
    def test_a_large_generated_file_is_not_held_to_the_upload_cap(self):
        """The compiled case merges files each already accepted; the upload cap must not
        reject a legitimate export of a large case (§10.3)."""
        oversized = make_pdf() + b"\n%" + b"x" * (settings.MAX_UPLOAD_BYTES + 1024)

        document = create_document(
            process=self.process,
            step_number=5,
            document_type=COMPILED_DOC_TYPE,
            input_source=Document.InputSource.SYSTEM_GENERATED,
            content=oversized,
            actor=self.admin,
        )
        self.assertGreater(document.size_bytes, settings.MAX_UPLOAD_BYTES)

    def test_an_upload_is_still_capped(self):
        oversized = make_pdf() + b"\n%" + b"x" * (settings.MAX_UPLOAD_BYTES + 1024)

        with self.assertRaises(PayloadTooLarge):
            create_document(
                process=self.process,
                step_number=1,
                document_type="ClientID",
                input_source=Document.InputSource.IMPORTED,
                content=oversized,
                actor=self.admin,
            )


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
