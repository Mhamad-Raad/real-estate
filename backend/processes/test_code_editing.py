"""The office may choose a case number by hand, and the sequence resumes from it (UC-062).

The allocator counts "highest ever issued + 1" over `all_objects` (§3.8), so choosing A15 while
the sequence sits at A12 is enough on its own to make the next automatic number A16. What these
pin is that the choosing is allowed, that it cannot produce a duplicate or a number belonging to
another category, and that a retired number stays retired.
"""

import tempfile
from pathlib import Path

from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from catalog.models import Category
from clients.factories import client_data, make_client

from .models import Process
from .services import create_process


class ChoosingACodeAtIntakeTests(APITestCase):
    def setUp(self):
        self.lawyer = User.objects.create_user("code_lw", password="pw12345678")
        self.category = Category.objects.create(code="A", name="A")
        self.other_category = Category.objects.create(code="B", name="B")
        self.client.force_authenticate(self.lawyer)

    def _open(self, pid, **extra):
        return self.client.post(
            reverse("process-list"),
            {"client_data": client_data(pid=pid), "category": self.category.id, **extra},
            format="json",
        )

    def test_a_case_opened_without_a_code_still_gets_the_next_one(self):
        resp = self._open("199001110001")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Process.objects.get(pk=resp.data["id"]).unique_code, "A1")

    def test_the_office_may_choose_where_the_sequence_resumes(self):
        self._open("199001110002")  # A1
        resp = self._open("199001110003", unique_code="A15")

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Process.objects.get(pk=resp.data["id"]).unique_code, "A15")

    def test_the_automatic_sequence_then_continues_past_the_chosen_number(self):
        """The point of the request: after jumping to A15 the next case must be A16, not A2."""
        self._open("199001110004")  # A1
        self._open("199001110005", unique_code="A15")

        resp = self._open("199001110006")

        self.assertEqual(Process.objects.get(pk=resp.data["id"]).unique_code, "A16")

    def test_a_number_already_issued_is_refused(self):
        self._open("199001110007", unique_code="A15")
        resp = self._open("199001110008", unique_code="A15")

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("unique_code", resp.data)

    def test_a_number_belonging_to_a_deleted_case_stays_retired(self):
        """A number is retired for ever once issued — the office's own rule, and the reason the
        allocator counts over `all_objects` rather than the live rows."""
        first = self._open("199001110009", unique_code="A20")
        Process.objects.filter(pk=first.data["id"]).update(is_deleted=True)

        resp = self._open("199001110010", unique_code="A20")

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_a_code_from_another_category_is_refused(self):
        resp = self._open("199001110011", unique_code="B7")

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("unique_code", resp.data)

    def test_a_code_that_is_not_a_number_after_the_letter_is_refused(self):
        self.assertEqual(
            self._open("199001110012", unique_code="A15b").status_code,
            status.HTTP_400_BAD_REQUEST,
        )


class EditingACodeAfterwardsTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user("cod_adm", password="pw12345678", role=User.Role.ADMIN)
        self.lawyer = User.objects.create_user("cod_lw", password="pw12345678")
        self.category = Category.objects.create(code="A", name="A")
        self.person = make_client(pid="199002220001", category=self.category)
        self.process = create_process(
            client=self.person,
            assigned_lawyer=self.lawyer,
            actor=self.lawyer,
            category=self.category,
        )
        self.client.force_authenticate(self.lawyer)

    def _patch(self, **body):
        return self.client.patch(
            reverse("process-detail", args=[self.process.id]),
            {"version": self.process.version, **body},
            format="json",
        )

    def test_the_assigned_lawyer_may_correct_the_number(self):
        resp = self._patch(unique_code="A15")

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.process.refresh_from_db()
        self.assertEqual(self.process.unique_code, "A15")

    def test_a_later_case_continues_from_the_corrected_number(self):
        self._patch(unique_code="A15")
        self.client.force_authenticate(self.admin)

        resp = self.client.post(
            reverse("process-list"),
            {"client_data": client_data(pid="199002220002"), "category": self.category.id},
            format="json",
        )

        self.assertEqual(Process.objects.get(pk=resp.data["id"]).unique_code, "A16")

    def test_a_number_another_live_case_holds_is_refused(self):
        other = make_client(pid="199002220003", category=self.category)
        taken = create_process(
            client=other, assigned_lawyer=self.lawyer, actor=self.lawyer, category=self.category
        )

        resp = self._patch(unique_code=taken.unique_code)

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("unique_code", resp.data)

    def test_keeping_the_same_number_is_not_a_collision_with_itself(self):
        resp = self._patch(unique_code=self.process.unique_code)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_a_case_cannot_be_left_without_a_number(self):
        """An unnumbered case cannot be found on the office's printed code list (§6.8)."""
        self.assertEqual(self._patch(unique_code="").status_code, status.HTTP_400_BAD_REQUEST)

    def test_a_lawyer_who_is_not_the_assignee_still_cannot_touch_it(self):
        stranger = User.objects.create_user("cod_str", password="pw12345678")
        self.client.force_authenticate(stranger)

        self.assertEqual(self._patch(unique_code="A15").status_code, status.HTTP_403_FORBIDDEN)


@override_settings(DOCUMENTS_ROOT=Path(tempfile.mkdtemp()))
class CorrectingACodeMovesThePapersTests(APITestCase):
    """The case number *is* part of the document store's path since UC-060, so UC-062's edit has
    to move the files with it — or the archive the office browses by hand keeps the old number.
    """

    def setUp(self):
        self.lawyer = User.objects.create_user("mov_lw", password="pw12345678")
        self.category = Category.objects.create(code="M", name="M")
        self.process = create_process(
            client=make_client(pid="MOVE-1", category=self.category),
            assigned_lawyer=self.lawyer,
            actor=self.lawyer,
            category=self.category,
        )
        self.document = self._document()
        self.client.force_authenticate(self.lawyer)

    def _document(self):
        from documents import filestore
        from documents.factories import make_pdf
        from documents.models import Document
        from documents.services import compose_location

        display, rel = compose_location(process=self.process, document_type="ClientID")
        # Real bytes on disk: the re-file moves the file, so a row with no file behind it would
        # test the wrong path.
        filestore.write_pdf(rel, make_pdf())
        return Document.objects.create(
            process=self.process,
            step_number=1,
            document_type="ClientID",
            file_path=str(rel),
            display_filename=display,
            sha256="a" * 64,
            size_bytes=1,
            uploaded_by=self.lawyer,
        )

    def test_the_case_folder_follows_the_new_number(self):
        self.assertIn("M1_MOVE-1", self.document.file_path)

        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client.patch(
                reverse("process-detail", args=[self.process.id]),
                {"unique_code": "M15", "version": self.process.version},
                format="json",
            )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.document.refresh_from_db()
        self.assertIn("M15_MOVE-1", self.document.file_path)
        self.assertNotIn("M1_MOVE-1", self.document.file_path)

    def test_the_download_name_follows_it_too(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.client.patch(
                reverse("process-detail", args=[self.process.id]),
                {"unique_code": "M15", "version": self.process.version},
                format="json",
            )

        self.document.refresh_from_db()
        self.assertTrue(self.document.display_filename.startswith("M15_"))

    def test_the_short_id_survives_the_move(self):
        sid = self.document.file_path.rsplit("__", 1)[-1]

        with self.captureOnCommitCallbacks(execute=True):
            self.client.patch(
                reverse("process-detail", args=[self.process.id]),
                {"unique_code": "M15", "version": self.process.version},
                format="json",
            )

        self.document.refresh_from_db()
        self.assertTrue(self.document.file_path.endswith(sid))

    def test_an_edit_that_leaves_the_code_alone_moves_nothing(self):
        """Re-filing on every header save would rewrite the filesystem for a notes edit."""
        before = self.document.file_path

        self.client.patch(
            reverse("process-detail", args=[self.process.id]),
            {"lawyer_notes": "just a note", "version": self.process.version},
            format="json",
        )

        self.document.refresh_from_db()
        self.assertEqual(self.document.file_path, before)


class CodeErrorsAreMachineReadableTests(APITestCase):
    """The office reads these in Sorani, so the reason travels as a code, not only a sentence."""

    def setUp(self):
        self.lawyer = User.objects.create_user("msg_lw", password="pw12345678")
        self.category = Category.objects.create(code="N", name="N")
        self.process = create_process(
            client=make_client(pid="MSG-1", category=self.category),
            assigned_lawyer=self.lawyer,
            actor=self.lawyer,
            category=self.category,
        )
        self.client.force_authenticate(self.lawyer)

    def _patch(self, code):
        return self.client.patch(
            reverse("process-detail", args=[self.process.id]),
            {"unique_code": code, "version": self.process.version},
            format="json",
        )

    def test_a_wrong_category_letter_names_itself(self):
        resp = self._patch("Z9")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(str(resp.data["code_error"][0]), "wrong_category")
        self.assertEqual(str(resp.data["expected_prefix"][0]), "N")

    def test_a_used_number_names_itself(self):
        taken = create_process(
            client=make_client(pid="MSG-2", category=self.category),
            assigned_lawyer=self.lawyer,
            actor=self.lawyer,
            category=self.category,
        )
        resp = self._patch(taken.unique_code)
        self.assertEqual(str(resp.data["code_error"][0]), "already_used")

    def test_an_empty_number_names_itself(self):
        self.assertEqual(str(self._patch("").data["code_error"][0]), "required")
