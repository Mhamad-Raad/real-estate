"""The office may choose a case number by hand, and the sequence resumes from it (UC-062).

The allocator counts "highest ever issued + 1" over `all_objects` (§3.8), so choosing A15 while
the sequence sits at A12 is enough on its own to make the next automatic number A16. What these
pin is that the choosing is allowed, that it cannot produce a duplicate or a number belonging to
another category, and that a retired number stays retired.
"""

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
