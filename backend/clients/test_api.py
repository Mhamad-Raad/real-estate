"""API tests for the clients endpoints — dedup check + married-spouse validation (§4, §5.7)."""

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User

from .models import Client


class ClientApiTests(APITestCase):
    def setUp(self):
        self.lawyer = User.objects.create_user("lw", password="pw12345678")
        self.client.force_authenticate(self.lawyer)
        self.existing = Client.objects.create(
            full_name="Karwan", pid="111", mother_full_name="Nasrin Hassan"
        )

    def test_duplicate_check_returns_pid_match(self):
        resp = self.client.post(
            reverse("client-duplicate-check"),
            {"pid": "111", "mother_full_name": "x"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual([c["id"] for c in resp.data["pid_matches"]], [self.existing.id])

    def test_married_client_requires_spouse_name(self):
        resp = self.client.post(
            reverse("client-list"),
            {
                "full_name": "Alan",
                "pid": "222",
                "mother_full_name": "Runak",
                "marital_status": "married",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("spouse_name", resp.data)

    def test_create_client_ok(self):
        resp = self.client.post(
            reverse("client-list"),
            {"full_name": "Alan", "pid": "222", "mother_full_name": "Runak"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
