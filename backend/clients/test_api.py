"""API tests for the clients endpoints — dedup check + married-spouse validation (§4, §5.7)."""

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User

from .models import Client
from .factories import client_data, make_client


class ClientApiTests(APITestCase):
    def setUp(self):
        self.lawyer = User.objects.create_user("lw", password="pw12345678")
        self.client.force_authenticate(self.lawyer)
        self.existing = make_client(
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

    def post_client(self, **overrides):
        payload = client_data(full_name="Alan", pid="222", mother_full_name="Runak", **overrides)
        return self.client.post(reverse("client-list"), payload, format="json")

    def test_married_client_requires_every_spouse_field(self):
        """The letter prints a spouse row of name / birth date / mother — all three or none."""
        for field in ("spouse_name", "spouse_date_of_birth", "spouse_mother_full_name"):
            with self.subTest(missing=field):
                payload = client_data(
                    full_name="Alan",
                    pid="222",
                    mother_full_name="Runak",
                    marital_status="married",
                )
                payload.pop(field)
                resp = self.client.post(reverse("client-list"), payload, format="json")
                self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn(field, resp.data)

    def test_birth_date_is_required(self):
        payload = client_data(full_name="Alan", pid="222", mother_full_name="Runak")
        payload.pop("date_of_birth")

        resp = self.client.post(reverse("client-list"), payload, format="json")

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("date_of_birth", resp.data)

    def test_unmarried_client_never_keeps_spouse_details(self):
        """A divorce must not leave the former spouse printed on the next generated letter."""
        married = make_client(
            full_name="Dashne",
            pid="333",
            mother_full_name="Nian",
            marital_status="married",
            created_by=self.lawyer,  # a lawyer may only edit clients they entered (§4.2)
        )

        resp = self.client.patch(
            reverse("client-detail", args=[married.id]),
            {"marital_status": "divorced", "version": married.version},
            format="json",
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        married.refresh_from_db()
        self.assertEqual(married.spouse_name, "")
        self.assertEqual(married.spouse_mother_full_name, "")
        self.assertIsNone(married.spouse_date_of_birth)

    def test_create_client_ok(self):
        resp = self.post_client()

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_married_client_with_full_spouse_details_is_accepted(self):
        resp = self.post_client(marital_status="married")

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
