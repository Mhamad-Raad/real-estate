"""The admin restore desk: seeing what has been soft-deleted, so it can be brought back (UC-063).

Nothing in this system is ever hard-deleted (§11.1), but until now the deleted rows were invisible
— `restore` could only be reached by someone who already knew the id. The listing is admin-only,
like `restore` itself, and reads through `all_objects`.
"""

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from catalog.models import Category
from clients.factories import make_client
from clients.models import Client

from .models import Process
from .services import create_process


class RestoreDeskTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user("desk_adm", password="pw12345678", role=User.Role.ADMIN)
        self.lawyer = User.objects.create_user("desk_lw", password="pw12345678")
        self.category = Category.objects.create(code="D", name="D")
        self.person = make_client(full_name="Binned", pid="199003330001", category=self.category)
        self.process = create_process(
            client=self.person,
            assigned_lawyer=self.lawyer,
            actor=self.lawyer,
            category=self.category,
        )
        self.kept = create_process(
            client=make_client(full_name="Kept", pid="199003330002", category=self.category),
            assigned_lawyer=self.lawyer,
            actor=self.lawyer,
            category=self.category,
        )
        self.client.force_authenticate(self.admin)
        self.client.delete(reverse("process-detail", args=[self.process.id]))

    def _rows(self, url):
        payload = self.client.get(url).data
        return payload["results"] if isinstance(payload, dict) and "results" in payload else payload

    def test_a_deleted_case_is_listed_and_a_live_one_is_not(self):
        ids = [row["id"] for row in self._rows(reverse("process-deleted"))]
        self.assertIn(self.process.id, ids)
        self.assertNotIn(self.kept.id, ids)

    def test_the_beneficiary_released_with_the_case_is_listed_too(self):
        """They were deleted by the cascade (UC-061), so this is where they are found again."""
        ids = [row["id"] for row in self._rows(reverse("client-deleted"))]
        self.assertIn(self.person.id, ids)

    def test_the_listing_carries_the_case_number_so_a_row_can_be_identified(self):
        row = next(r for r in self._rows(reverse("process-deleted")) if r["id"] == self.process.id)
        self.assertEqual(row["unique_code"], self.process.unique_code)

    def test_a_lawyer_cannot_see_the_desk(self):
        self.client.force_authenticate(self.lawyer)
        self.assertEqual(
            self.client.get(reverse("process-deleted")).status_code, status.HTTP_403_FORBIDDEN
        )
        self.assertEqual(
            self.client.get(reverse("client-deleted")).status_code, status.HTTP_403_FORBIDDEN
        )

    def test_restoring_from_the_desk_clears_the_row_from_it(self):
        self.client.post(reverse("process-restore", args=[self.process.id]))

        self.assertNotIn(
            self.process.id, [row["id"] for row in self._rows(reverse("process-deleted"))]
        )
        self.assertFalse(Process.objects.get(pk=self.process.id).is_deleted)
        # And the beneficiary came back with it, so neither desk still lists them.
        self.assertNotIn(self.person.id, [r["id"] for r in self._rows(reverse("client-deleted"))])
        self.assertTrue(Client.objects.filter(pk=self.person.id).exists())
