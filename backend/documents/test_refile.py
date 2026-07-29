"""Re-filing after the data a path was composed from changes (§6.7)."""

import tempfile
from pathlib import Path

from django.conf import settings
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.models import User
from catalog.models import Category
from clients.factories import make_client
from common.models import ActivityLog
from documents.factories import make_pdf
from documents.models import Document
from documents.refile import refile_client_documents
from documents.services import create_document
from processes.services import create_process


class RefileTests(APITestCase):
    def setUp(self):
        # A pristine store per test. A root shared across the class would accumulate each test's
        # files in the same person folder, so "is this folder now empty?" could never be asked.
        self.enterContext(override_settings(DOCUMENTS_ROOT=Path(tempfile.mkdtemp())))
        self.admin = User.objects.create_user(
            username="adm", password="pw12345678", role=User.Role.ADMIN
        )
        self.lawyer = User.objects.create_user(username="lw", password="pw12345678")
        self.category_a = Category.objects.create(code="A", name="Category A")
        self.category_b = Category.objects.create(code="B", name="Category B")
        self.client_row = make_client(full_name="Old Name", pid="PID-1", mother_full_name="M")
        self.process = create_process(
            client=self.client_row,
            assigned_lawyer=self.lawyer,
            actor=self.admin,
            category=self.category_a,
        )
        self.document = create_document(
            process=self.process,
            step_number=1,
            document_type="ClientID",
            input_source=Document.InputSource.IMPORTED,
            content=make_pdf(),
            actor=self.lawyer,
        )

    def _refile(self, **kwargs):
        """Re-file and run the on-commit callbacks — the move is deferred to commit (§6.7)."""
        with self.captureOnCommitCallbacks(execute=True):
            return refile_client_documents(self.client_row, actor=self.admin, **kwargs)

    def test_a_name_correction_does_not_touch_the_filesystem(self):
        """The whole point of shortening the on-disk name: the person is no longer part of it."""
        before_path = self.document.file_path
        self.client_row.full_name = "Corrected Name"
        self.client_row.save(update_fields=["full_name"])

        self._refile()

        self.document.refresh_from_db()
        self.assertEqual(self.document.file_path, before_path)
        self.assertIn("Corrected_Name", self.document.display_filename)
        self.assertTrue((settings.DOCUMENTS_ROOT / self.document.file_path).exists())

    def test_a_category_change_moves_the_file_to_the_new_folder(self):
        old = settings.DOCUMENTS_ROOT / self.document.file_path
        self.assertTrue(str(self.document.file_path).startswith("A/"))

        self.process.category = self.category_b
        self.process.save(update_fields=["category"])
        self._refile()

        self.document.refresh_from_db()
        self.assertTrue(self.document.file_path.startswith("B/"))
        self.assertTrue((settings.DOCUMENTS_ROOT / self.document.file_path).exists())
        self.assertFalse(old.exists())

    def test_a_pid_correction_moves_the_person_folder(self):
        """A misread card number is corrected often enough to matter, and the folder is keyed
        by the PID (§6.7)."""
        old = settings.DOCUMENTS_ROOT / self.document.file_path
        self.client_row.pid = "PID-CORRECTED"
        self.client_row.save(update_fields=["pid"])

        self._refile()

        self.document.refresh_from_db()
        self.assertIn("/PID-CORRECTED/", f"/{self.document.file_path}")
        self.assertTrue((settings.DOCUMENTS_ROOT / self.document.file_path).exists())
        self.assertFalse(old.exists())

    def test_the_short_id_survives_the_move_so_the_file_stays_traceable(self):
        sid = self.document.file_path.rsplit("__", 1)[-1]
        self.client_row.pid = "PID-2"
        self.client_row.save(update_fields=["pid"])
        self._refile()

        self.document.refresh_from_db()
        self.assertTrue(self.document.file_path.endswith(sid))
        self.assertTrue(self.document.display_filename.endswith(sid))

    def test_re_filing_is_audited(self):
        self.client_row.pid = "PID-3"
        self.client_row.save(update_fields=["pid"])
        self._refile()

        entry = ActivityLog.objects.filter(
            entity_type="Document", entity_id=str(self.document.id), action="update"
        ).latest("created_at")
        self.assertEqual(entry.after["reason"], "re-filed")
        self.assertNotEqual(entry.before["file_path"], entry.after["file_path"])

    def test_a_document_already_in_place_is_left_alone(self):
        self.assertEqual(self._refile(), [])

    def test_running_it_twice_changes_nothing_the_second_time(self):
        self.client_row.pid = "PID-4"
        self.client_row.save(update_fields=["pid"])
        self.assertEqual(len(self._refile()), 1)
        self.assertEqual(self._refile(), [])

    def test_the_emptied_person_folder_is_removed_with_the_move(self):
        old_dir = (settings.DOCUMENTS_ROOT / self.document.file_path).parent
        self.client_row.pid = "PID-5"
        self.client_row.save(update_fields=["pid"])
        self._refile()

        self.assertFalse(old_dir.exists())
        # The category folder above it is fixed and must survive.
        self.assertTrue(old_dir.parent.exists())

    def test_a_folder_still_holding_a_soft_deleted_file_is_kept(self):
        """That row still points at it — restoring the document must not find a hole."""
        second = create_document(
            process=self.process,
            step_number=1,
            document_type="RealEstate",
            input_source=Document.InputSource.IMPORTED,
            content=make_pdf(),
            actor=self.lawyer,
        )
        second.is_deleted = True
        second.save(update_fields=["is_deleted"])
        old_dir = (settings.DOCUMENTS_ROOT / self.document.file_path).parent

        self.client_row.pid = "PID-6"
        self.client_row.save(update_fields=["pid"])
        self._refile()

        self.assertTrue(old_dir.exists())
        self.assertTrue((settings.DOCUMENTS_ROOT / second.file_path).exists())

    def test_a_path_without_a_short_id_is_not_mangled(self):
        """A hand-placed file has no `__<shortid>`; splicing the old path in as one would write
        outside the folder the rename was aiming at."""
        self.document.file_path = "A/PID-1/legacy-name.pdf"
        self.document.save(update_fields=["file_path"])
        (settings.DOCUMENTS_ROOT / "A" / "PID-1").mkdir(parents=True, exist_ok=True)
        (settings.DOCUMENTS_ROOT / self.document.file_path).write_bytes(make_pdf())

        self.client_row.pid = "PID-7"
        self.client_row.save(update_fields=["pid"])
        self._refile()

        self.document.refresh_from_db()
        self.assertNotIn("legacy-name", self.document.file_path)
        self.assertEqual(self.document.file_path.count("/"), 2)
        self.assertTrue((settings.DOCUMENTS_ROOT / self.document.file_path).exists())

    def test_correcting_a_pid_through_the_api_re_files_automatically(self):
        self.client.force_authenticate(self.admin)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.patch(
                reverse("client-detail", args=[self.client_row.id]),
                {"pid": "PID-VIA-API", "version": self.client_row.version},
                format="json",
            )
        self.assertEqual(response.status_code, 200)

        self.document.refresh_from_db()
        self.assertIn("/PID-VIA-API/", f"/{self.document.file_path}")
        self.assertTrue((settings.DOCUMENTS_ROOT / self.document.file_path).exists())
