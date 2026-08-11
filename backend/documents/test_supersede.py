"""Regenerating removes the old file; a person deleting one does not (§6.6, §10.3, UC-063).

The store grew on every press of Generate: the row was soft-deleted but the PDF stayed on disk for
ever. Removing it is safe **only** for a superseded generated document — a user-deleted one is
restorable from the Deleted-items desk, and a restore that brings back a row whose file is gone
would produce a case that fails at the next compile. That is the line these tests hold.
"""

import tempfile
from datetime import date
from pathlib import Path

from django.conf import settings
from django.test import TestCase, override_settings

from accounts.models import User
from catalog.models import Category
from clients.models import Client
from common.models import ActivityLog
from processes.services import create_process

from .factories import make_pdf
from .models import Document
from .services import create_document, supersede_generated_documents


@override_settings(DOCUMENTS_ROOT=Path(tempfile.mkdtemp()))
class SupersedeTests(TestCase):
    def setUp(self):
        self.actor = User.objects.create_user("sup", password="pw12345678")
        category = Category.objects.create(code="S", name="S")
        client = Client.objects.create(
            full_name="Person", pid="199900008888", mother_full_name="M",
            date_of_birth=date(1990, 1, 1), category=category,
        )
        self.process = create_process(
            client=client, category=category, assigned_lawyer=self.actor, actor=self.actor
        )

    def _make(self, document_type, step=1):
        return create_document(
            process=self.process, step_number=step, document_type=document_type,
            input_source=Document.InputSource.SYSTEM_GENERATED,
            content=make_pdf(1), actor=self.actor,
        )

    def _path(self, document):
        return Path(settings.DOCUMENTS_ROOT) / document.file_path

    def test_a_regenerated_letter_leaves_no_file_behind(self):
        old = self._make("EligibilityLetter")
        self.assertTrue(self._path(old).is_file())

        supersede_generated_documents(
            process=self.process, document_type="EligibilityLetter", actor=self.actor, job_id=7
        )

        old.refresh_from_db()
        self.assertTrue(old.is_deleted)
        self.assertFalse(self._path(old).is_file(), "the superseded PDF is still on disk")

    def test_the_audit_row_survives_the_file(self):
        """The trail still shows a letter existed, who replaced it and with which job — that is
        what makes deleting the bytes acceptable."""
        old = self._make("EligibilityLetter")

        supersede_generated_documents(
            process=self.process, document_type="EligibilityLetter", actor=self.actor, job_id=7
        )

        row = ActivityLog.objects.get(
            entity_type="Document", entity_id=str(old.pk), action=ActivityLog.Action.DELETE
        )
        self.assertEqual(row.before["superseded_by_job"], 7)
        self.assertTrue(row.before["file_removed"])

    def test_a_recompiled_export_leaves_no_file_behind(self):
        old = self._make("CompiledCase", step=5)

        supersede_generated_documents(
            process=self.process, document_type="CompiledCase", actor=self.actor, job_id=9
        )

        self.assertFalse(self._path(old).is_file())

    def test_it_only_touches_the_type_it_was_asked_for(self):
        """A regenerate must not sweep the papers the case was built from."""
        keep = self._make("ClientID")
        self._make("EligibilityLetter")

        supersede_generated_documents(
            process=self.process, document_type="EligibilityLetter", actor=self.actor
        )

        keep.refresh_from_db()
        self.assertFalse(keep.is_deleted)
        self.assertTrue(self._path(keep).is_file())

    def test_a_USER_deleted_document_keeps_its_file_so_restore_works(self):
        """The line that matters: the restore desk (UC-063) brings a row back, and it must still
        have its PDF. Deleting through the API must never remove the file."""
        document = self._make("ClientID")
        path = self._path(document)

        # What the viewset's soft-delete does — the ordinary delete path, not a supersede.
        document.is_deleted = True
        document.save(update_fields=["is_deleted"])

        self.assertTrue(path.is_file(), "a restorable document lost its file")

    def test_an_already_missing_file_does_not_raise(self):
        """The store is a bind mount the office can reach by hand (§2.5), so a file may be gone."""
        old = self._make("EligibilityLetter")
        self._path(old).unlink()

        supersede_generated_documents(
            process=self.process, document_type="EligibilityLetter", actor=self.actor
        )

        old.refresh_from_db()
        self.assertTrue(old.is_deleted)


@override_settings(DOCUMENTS_ROOT=Path(tempfile.mkdtemp()))
class ListDownloadIsOneShotTests(TestCase):
    """A list letter is collected once, then removed (§6.8, office decision 2026-08-11).

    It belongs to no case — it is a bulk export of many citizens' details that the office saves or
    prints on the spot — so keeping every one ever produced grew the store for nothing and left
    personal data sitting in `_generated` indefinitely.
    """

    def setUp(self):
        from rest_framework.test import APIClient

        from .models import DocumentTemplate, GenerationJob

        self.actor = User.objects.create_user("dl", password="pw12345678", role=User.Role.ADMIN)
        template = DocumentTemplate.objects.create(
            template_type=DocumentTemplate.TemplateType.PROCESS_LIST,
            name="L", file_path="x/y.docx", sha256="0" * 64,
        )
        out = Path(settings.DOCUMENTS_ROOT) / "_generated/lists/list_1.pdf"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(make_pdf(1))
        self.path = out
        self.job = GenerationJob.objects.create(
            kind=GenerationJob.Kind.PROCESS_LIST, template=template,
            status=GenerationJob.Status.DONE, output_path="_generated/lists/list_1.pdf",
            process_ids=[], requested_by=self.actor,
        )
        self.api = APIClient()
        self.api.force_authenticate(self.actor)

    def test_the_first_download_returns_the_pdf(self):
        resp = self.api.get(f"/api/v1/generation-jobs/{self.job.id}/file/")

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(b"".join(resp.streaming_content).startswith(b"%PDF"))

    def test_the_file_is_gone_from_the_store_afterwards(self):
        self.api.get(f"/api/v1/generation-jobs/{self.job.id}/file/")

        self.assertFalse(self.path.is_file())

    def test_a_second_attempt_says_so_plainly_rather_than_looking_broken(self):
        self.api.get(f"/api/v1/generation-jobs/{self.job.id}/file/")

        resp = self.api.get(f"/api/v1/generation-jobs/{self.job.id}/file/")

        self.assertEqual(resp.status_code, 404)
        self.assertIn("already been downloaded", str(resp.data["detail"]))

    def test_the_job_row_still_records_what_was_produced(self):
        """The file goes; the trail of who exported whose data does not (§11)."""
        self.api.get(f"/api/v1/generation-jobs/{self.job.id}/file/")
        self.job.refresh_from_db()

        self.assertEqual(self.job.output_path, "_generated/lists/list_1.pdf")
        self.assertEqual(self.job.status, self.job.Status.DONE)
