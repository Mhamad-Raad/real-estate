"""The fast-entry door for the office's paper backlog (UC-114).

Thousands of finished allocations exist only on paper. What comes in is the fields that make a
case findable plus ONE PDF — the case file, which is the same document step 5 compiles for a case
worked here. Everything else stays empty, and the case is badged so the empty steps read as
history rather than as work nobody finished.
"""

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from catalog.document_types import COMPILED_CASE
from catalog.models import Category
from clients.models import Client
from common.models import ActivityLog
from documents.factories import make_pdf
from documents.models import Document

from .models import Process


class FastEntryTests(APITestCase):
    def setUp(self):
        self.lawyer = User.objects.create_user("fe_lawyer", password="pw12345678")
        self.admin = User.objects.create_user(
            "fe_admin", password="pw12345678", role=User.Role.ADMIN
        )
        self.category = Category.objects.create(code="A", name="A")
        self.client.force_authenticate(self.lawyer)

    def _post(self, **over):
        payload = {
            "full_name": "Karwan Ahmed",
            "pid": "197712120099",
            "mother_full_name": "Nask Ali",
            "date_of_birth": "1977-12-12",
            "category": self.category.id,
            "land_id": "4472",
            "mark_complete": "true",
            "file": SimpleUploadedFile("case.pdf", make_pdf(3), content_type="application/pdf"),
        }
        payload.update(over)
        return self.client.post(reverse("process-fast-entry"), payload, format="multipart")

    def test_one_request_creates_the_person_the_case_and_the_file(self):
        resp = self._post()

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        process = Process.objects.get(pk=resp.data["id"])
        self.assertEqual(process.client.full_name, "Karwan Ahmed")
        self.assertEqual(process.land_id, "4472")
        self.assertEqual(process.documents.count(), 1)

    def test_the_one_pdf_is_filed_as_the_case_file_step_5_would_have_compiled(self):
        resp = self._post()

        document = Document.objects.get(process_id=resp.data["id"])

        self.assertEqual(document.document_type, COMPILED_CASE)
        self.assertEqual(document.step_number, 5)
        # A person imported it, and the audit trail must not claim the system produced it.
        self.assertEqual(document.input_source, Document.InputSource.IMPORTED)
        self.assertEqual(document.page_count, 3)

    def test_the_case_takes_the_next_code_like_any_other(self):
        """The office is entering the backlog in order, so the running sequence is the point —
        there is no code input and nothing is typed."""
        first = self._post()
        second = self._post(full_name="Someone Else", pid="196505050088")

        self.assertEqual(first.data["unique_code"], "A1")
        self.assertEqual(second.data["unique_code"], "A2")

    def test_the_case_is_badged_as_backlog(self):
        resp = self._post()

        self.assertTrue(resp.data["fast_entry"])
        self.assertTrue(Process.objects.get(pk=resp.data["id"]).fast_entry)

    def test_an_ordinary_case_is_not(self):
        resp = self.client.post(
            reverse("process-list"),
            {
                "client_data": {
                    "full_name": "Walk In",
                    "pid": "198001010077",
                    "mother_full_name": "Mother",
                    "date_of_birth": "1980-01-01",
                },
                "category": self.category.id,
            },
            format="json",
        )

        self.assertFalse(Process.objects.get(pk=resp.data["id"]).fast_entry)

    def test_the_person_typing_it_in_becomes_the_lawyer(self):
        resp = self._post()

        self.assertEqual(Process.objects.get(pk=resp.data["id"]).assigned_lawyer_id, self.lawyer.id)

    def test_it_closes_the_case_over_its_empty_steps_when_asked(self):
        resp = self._post()

        process = Process.objects.get(pk=resp.data["id"])

        self.assertEqual(process.overall_status, Process.OverallStatus.COMPLETE)
        self.assertEqual(process.completed_by_id, self.lawyer.id)

    def test_it_leaves_an_unfinished_one_open(self):
        resp = self._post(mark_complete="false")

        process = Process.objects.get(pk=resp.data["id"])

        self.assertNotEqual(process.overall_status, Process.OverallStatus.COMPLETE)

    def test_a_lawyer_may_close_one_without_being_an_admin(self):
        """Forcing an ordinary case past missing files is admin-only (§10.3). A backlog case has
        no requirements to force past — it is a finished file being recorded, and in a two-person
        office both of them are typing."""
        self.assertEqual(self._post().status_code, status.HTTP_201_CREATED)
        self.assertFalse(self.lawyer.is_admin)

    def test_the_same_national_id_is_refused_here_too(self):
        """The office's call: the duplicate rules are not relaxed for this door."""
        self._post()

        second = self._post(full_name="Same Person Again")

        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Client.objects.count(), 1)

    def test_a_flagged_duplicate_is_never_closed_behind_the_office(self):
        """Closing it would file a possible duplicate as a finished allocation and take it off
        every list a person would look at — the one thing "run the checks" cannot mean."""
        self._post(mark_complete="false")
        spouse_of_the_first = self._post(
            full_name="The Wife",
            pid="199003030044",
            mark_complete="true",
        )

        self.assertEqual(spouse_of_the_first.status_code, status.HTTP_201_CREATED)

    def test_the_form_still_obeys_the_offices_field_rules(self):
        """Validated through `ClientSerializer`, so the PID rule (§4.1) cannot drift from the
        Clients API just because this is a different door. A **short** ID is legitimate here —
        the backlog is full of them (2026-08-30) — so the proof is a run that is too long."""
        resp = self._post(pid="1234567890123")  # one longer than a card can carry

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("pid", resp.data)

    def test_a_category_is_required_because_the_code_comes_from_it(self):
        resp = self._post(category="")

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("category", resp.data)

    def test_nothing_is_left_behind_when_the_file_is_rejected(self):
        """One act, or none: an abandoned form must leave no half-created case, because nothing
        here is ever hard-deleted (§11.1)."""
        resp = self._post(
            file=SimpleUploadedFile("case.pdf", b"not a pdf at all", content_type="application/pdf")
        )

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Process.objects.exists())
        self.assertFalse(Client.objects.exists())

    def test_a_whole_case_file_is_not_refused_for_being_bigger_than_one_paper(self):
        """A scan of a twenty-page file is a compiled case, not a single paper (UC-114). The size
        rule has to be the same one on the way **in** as on the way down — `read_upload` refuses
        an upload before reading it, and capping that at the single-paper limit made the larger
        bound below it unreachable."""
        from django.conf import settings

        from documents.services import size_limit_for

        self.assertEqual(
            size_limit_for(
                document_type=COMPILED_CASE, input_source=Document.InputSource.IMPORTED
            ),
            settings.MAX_GENERATED_BYTES,
        )
        self.assertEqual(
            size_limit_for(
                document_type="SignedAgreement", input_source=Document.InputSource.IMPORTED
            ),
            settings.MAX_UPLOAD_BYTES,
        )

    def test_the_whole_act_is_audited(self):
        resp = self._post()

        entities = set(
            ActivityLog.objects.filter(actor=self.lawyer).values_list("entity_type", flat=True)
        )

        self.assertLessEqual({"Client", "Process", "Document"}, entities)
        self.assertTrue(ActivityLog.objects.filter(entity_id=resp.data["id"]).exists())
