"""UC-118: the stored compiled exports are retired; a scanned case file is never touched."""

import tempfile
from io import StringIO
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase, override_settings

from accounts.models import User
from clients.factories import make_client
from common.models import ActivityLog
from processes.services import create_process

from .factories import make_pdf
from .models import Document
from .services import create_document


@override_settings(DOCUMENTS_ROOT=Path(tempfile.mkdtemp()))
class RetireCompiledExportsTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("adm", password="pw12345678", role=User.Role.ADMIN)
        self.process = create_process(
            client=make_client(full_name="B", pid="C-1", mother_full_name="M"),
            assigned_lawyer=self.admin,
            actor=self.admin,
        )

    def _compiled(self, source) -> Document:
        return create_document(
            process=self.process, step_number=5, document_type="CompiledCase",
            input_source=source, content=make_pdf(1), actor=self.admin,
        )

    def _path(self, document) -> Path:
        return Path(settings.DOCUMENTS_ROOT) / document.file_path

    def _run(self, *args) -> str:
        out = StringIO()
        call_command("retire_compiled_exports", *args, stdout=out)
        return out.getvalue()

    def test_reports_without_apply_and_removes_nothing(self):
        export = self._compiled(Document.InputSource.SYSTEM_GENERATED)

        report = self._run()

        self.assertIn("1 compiled export(s)", report)
        export.refresh_from_db()
        self.assertFalse(export.is_deleted)
        self.assertTrue(self._path(export).is_file())

    def test_apply_retires_the_row_its_file_and_audits_it(self):
        export = self._compiled(Document.InputSource.SYSTEM_GENERATED)

        self._run("--apply")

        export.refresh_from_db()
        self.assertTrue(export.is_deleted)
        self.assertFalse(self._path(export).is_file())
        row = ActivityLog.objects.get(entity_type="Document", entity_id=str(export.pk), action=ActivityLog.Action.DELETE)
        self.assertTrue(row.before["file_removed"])

    def test_a_scanned_case_file_is_the_only_copy_and_stays(self):
        """The backlog door files the paper case itself as a CompiledCase (UC-114)."""
        scan = self._compiled(Document.InputSource.IMPORTED)

        report = self._run("--apply")

        self.assertIn("Nothing to do", report)
        scan.refresh_from_db()
        self.assertFalse(scan.is_deleted)
        self.assertTrue(self._path(scan).is_file())

    def test_running_twice_does_nothing_the_second_time(self):
        self._compiled(Document.InputSource.SYSTEM_GENERATED)
        self._run("--apply")

        self.assertIn("Nothing to do", self._run("--apply"))
