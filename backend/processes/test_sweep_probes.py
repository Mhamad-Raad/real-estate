"""Probes for the batch-11 proactive sweep (UC-035): who may be handed a brand-new case."""

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from catalog.models import Category
from clients.factories import client_data

from .models import Process


class AssignableLawyerTests(APITestCase):
    """A case may only be opened against someone who can still sign in and work it (§7.2)."""

    def setUp(self):
        self.admin = User.objects.create_user(
            "sweep_admin", password="pw12345678", role=User.Role.ADMIN
        )
        self.gone = User.objects.create_user("sweep_gone", password="pw12345678")
        self.category = Category.objects.create(code="A", name="A")
        self.client.force_authenticate(self.admin)

    def _payload(self, assignee, pid):
        return {
            "client_data": client_data(pid=pid),
            "assigned_lawyer": assignee.id,
            "category": self.category.id,
        }

    def test_a_deactivated_lawyer_cannot_be_handed_a_new_case(self):
        self.gone.is_active = False
        self.gone.save(update_fields=["is_active"])
        resp = self.client.post(
            reverse("process-list"), self._payload(self.gone, "199505050001"), format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("assigned_lawyer", resp.data)
        self.assertFalse(Process.objects.filter(client__pid="199505050001").exists())

    def test_a_soft_deleted_lawyer_cannot_be_handed_a_new_case(self):
        self.gone.is_deleted = True
        self.gone.save(update_fields=["is_deleted"])
        resp = self.client.post(
            reverse("process-list"), self._payload(self.gone, "199505050002"), format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_an_active_lawyer_is_still_assignable(self):
        resp = self.client.post(
            reverse("process-list"), self._payload(self.gone, "199505050003"), format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Process.objects.get(pk=resp.data["id"]).assigned_lawyer_id, self.gone.id)

    def test_the_lawyers_endpoint_is_the_one_that_omits_them(self):
        """The dropdown source must not offer someone the API would then refuse."""
        self.gone.is_active = False
        self.gone.save(update_fields=["is_active"])
        listed = self.client.get(reverse("lawyers")).data
        self.assertNotIn("sweep_gone", [row["username"] for row in listed])
        self.assertIn("sweep_admin", [row["username"] for row in listed])
