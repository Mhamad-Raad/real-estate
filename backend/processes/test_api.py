"""API-level RBAC + optimistic-lock + override tests for the processes endpoints (§4, §7)."""

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from clients.models import Client

from .models import Process
from .services import create_process


class ProcessApiTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user("admin_a", password="pw12345678", role=User.Role.ADMIN)
        self.lawyer_a = User.objects.create_user("lawyer_a", password="pw12345678")
        self.lawyer_b = User.objects.create_user("lawyer_b", password="pw12345678")
        self.client_row = Client.objects.create(full_name="Ben", pid="900", mother_full_name="Mo")

    def test_list_requires_authentication(self):
        self.assertEqual(self.client.get(reverse("process-list")).status_code, 401)

    def test_lawyer_creates_process_assigned_to_self(self):
        self.client.force_authenticate(self.lawyer_a)
        resp = self.client.post(
            reverse("process-list"), {"client": self.client_row.id}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        process = Process.objects.get(pk=resp.data["id"])
        self.assertEqual(process.assigned_lawyer_id, self.lawyer_a.id)
        self.assertEqual(process.steps.count(), 5)

    def test_second_active_allocation_returns_409_not_500(self):
        create_process(
            client=self.client_row, assigned_lawyer=self.lawyer_a, actor=self.lawyer_a
        )
        self.client.force_authenticate(self.lawyer_a)
        resp = self.client.post(
            reverse("process-list"), {"client": self.client_row.id}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)

    def test_lawyer_cannot_edit_another_lawyers_process(self):
        process = create_process(
            client=self.client_row, assigned_lawyer=self.lawyer_a, actor=self.lawyer_a
        )
        self.client.force_authenticate(self.lawyer_b)
        resp = self.client.patch(
            reverse("process-detail", args=[process.id]),
            {"lawyer_notes": "hijack", "version": process.version},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_edit_any_process(self):
        process = create_process(
            client=self.client_row, assigned_lawyer=self.lawyer_a, actor=self.lawyer_a
        )
        self.client.force_authenticate(self.admin)
        resp = self.client.patch(
            reverse("process-detail", args=[process.id]),
            {"lawyer_notes": "admin note", "version": process.version},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_stale_version_conflicts_409(self):
        process = create_process(
            client=self.client_row, assigned_lawyer=self.lawyer_a, actor=self.lawyer_a
        )
        self.client.force_authenticate(self.lawyer_a)
        url = reverse("process-detail", args=[process.id])
        # First edit succeeds and bumps version 1 -> 2.
        self.client.patch(url, {"lawyer_notes": "v2", "version": 1}, format="json")
        # Second edit with the now-stale version 1 must conflict.
        resp = self.client.patch(url, {"lawyer_notes": "stale", "version": 1}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)

    def test_override_duplicate_is_admin_only(self):
        process = create_process(
            client=self.client_row,
            assigned_lawyer=self.lawyer_a,
            actor=self.lawyer_a,
            duplicate_flagged=True,
        )
        url = reverse("process-override-duplicate", args=[process.id])
        body = {"match_reason": "mother_name", "reason": "sibling"}

        self.client.force_authenticate(self.lawyer_a)
        self.assertEqual(self.client.post(url, body, format="json").status_code, 403)

        self.client.force_authenticate(self.admin)
        resp = self.client.post(url, body, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        process.refresh_from_db()
        self.assertFalse(process.duplicate_flagged)
