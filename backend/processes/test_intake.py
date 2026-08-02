"""Step-1 intake: the beneficiary and their case are created by one submit (§5, UC-024)."""

from unittest.mock import patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from clients.factories import client_data, make_client
from clients.models import Client

from .models import Process
from .services import DuplicateAllocation, create_process, intake_process


class IntakeApiTests(APITestCase):
    def setUp(self):
        self.lawyer = User.objects.create_user("intake_lawyer", password="pw12345678")
        self.client.force_authenticate(self.lawyer)

    def _payload(self, **overrides):
        return {"client_data": client_data(**{"pid": "199505054321", **overrides})}

    def test_creates_the_beneficiary_and_the_case_together(self):
        resp = self.client.post(reverse("process-list"), self._payload(), format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        process = Process.objects.get(pk=resp.data["id"])
        self.assertEqual(process.client.pid, "199505054321")
        self.assertEqual(process.assigned_lawyer_id, self.lawyer.id)
        self.assertEqual(process.steps.count(), 5)

    def test_land_details_are_saved_by_the_same_submit(self):
        payload = {**self._payload(), "land_id": "L-42", "land_address": "Street 9"}
        resp = self.client.post(reverse("process-list"), payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        process = Process.objects.get(pk=resp.data["id"])
        self.assertEqual((process.land_id, process.land_address), ("L-42", "Street 9"))

    def test_an_existing_beneficiary_still_works(self):
        existing = make_client(full_name="On File", pid="197007071111")
        resp = self.client.post(
            reverse("process-list"), {"client": existing.id}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Process.objects.get(pk=resp.data["id"]).client_id, existing.id)

    def test_rejects_both_an_existing_and_a_new_beneficiary(self):
        existing = make_client(pid="197007072222")
        payload = {"client": existing.id, **self._payload()}
        resp = self.client.post(reverse("process-list"), payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_neither(self):
        resp = self.client.post(reverse("process-list"), {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_a_pid_someone_else_holds_is_a_400_not_a_500(self):
        """`ix_client_pid_active` would otherwise raise IntegrityError → an HTTP 500 saying nothing.

        DRF derives the check from the partial UniqueConstraint, so it lands as a field error on
        `pid`; `assert_pid_is_free` is the backstop for the OCR path, which has no serializer.
        """
        make_client(full_name="Already Here", pid="196001011234")
        resp = self.client.post(
            reverse("process-list"), self._payload(pid="196001011234"), format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("pid", str(resp.data))

    def test_married_beneficiary_still_needs_the_full_spouse_set(self):
        """The nested serializer must enforce exactly what the Clients API does (§6.6)."""
        payload = {"client_data": client_data(pid="199505059999", marital_status="married")}
        payload["client_data"].pop("spouse_name")
        resp = self.client.post(reverse("process-list"), payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("spouse_name", str(resp.data))


class IntakeAtomicityTests(APITestCase):
    """The reason nothing is written before the submit: a half-created case is permanent (§11.1)."""

    def setUp(self):
        self.lawyer = User.objects.create_user("atomic_lawyer", password="pw12345678")

    def test_a_failure_after_the_client_leaves_no_orphan_behind(self):
        before = Client.objects.count()
        # The case create is the step that can fail on its own (duplicate allocation, lost race);
        # if the client survived that, an abandoned person would be stranded in the register.
        with patch("processes.services.create_process", side_effect=DuplicateAllocation()):
            with self.assertRaises(DuplicateAllocation):
                intake_process(
                    client_data=client_data(pid="200001019999"),
                    assigned_lawyer=self.lawyer,
                    actor=self.lawyer,
                )
        self.assertEqual(Client.objects.count(), before)
        self.assertFalse(Client.objects.filter(pid="200001019999").exists())

    def test_a_second_allocation_for_the_same_person_is_still_refused(self):
        existing = make_client(pid="200001018888")
        create_process(client=existing, assigned_lawyer=self.lawyer, actor=self.lawyer)
        self.client.force_authenticate(self.lawyer)
        resp = self.client.post(
            reverse("process-list"), {"client": existing.id}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
