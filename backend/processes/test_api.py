"""API-level RBAC + optimistic-lock + override tests for the processes endpoints (§4, §7)."""

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from catalog.models import Category
from clients.models import Client
from common.models import ActivityLog

from .models import Process
from .services import create_process
from clients.factories import make_client


class ProcessApiTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user("admin_a", password="pw12345678", role=User.Role.ADMIN)
        self.lawyer_a = User.objects.create_user("lawyer_a", password="pw12345678")
        self.lawyer_b = User.objects.create_user("lawyer_b", password="pw12345678")
        self.category = Category.objects.create(code="A", name="A")
        # Carrying the category is what lets a case be opened for this person without naming one
        # (UC-056: every case must be numberable).
        self.client_row = make_client(
            full_name="Ben", pid="900", mother_full_name="Mo", category=self.category
        )

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

    def test_a_lawyer_may_open_a_case_in_a_colleagues_name(self):
        """The office's rule (2026-08-06): whoever takes the papers in is not always who works the
        case. The name still has to be an assignable one (§7.2 layer 6) — that guard is separate."""
        self.client.force_authenticate(self.lawyer_a)
        resp = self.client.post(
            reverse("process-list"),
            {"client": self.client_row.id, "assigned_lawyer": self.lawyer_b.id},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            Process.objects.get(pk=resp.data["id"]).assigned_lawyer_id, self.lawyer_b.id
        )

    def test_a_case_still_cannot_be_opened_for_a_lawyer_who_has_left(self):
        self.lawyer_b.is_active = False
        self.lawyer_b.save(update_fields=["is_active"])
        self.client.force_authenticate(self.lawyer_a)
        resp = self.client.post(
            reverse("process-list"),
            {"client": self.client_row.id, "assigned_lawyer": self.lawyer_b.id},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("assigned_lawyer", resp.data)

    def test_list_can_filter_by_current_step(self):
        p1 = create_process(client=self.client_row, assigned_lawyer=self.lawyer_a, actor=self.lawyer_a)
        other = make_client(full_name="Two", pid="901", mother_full_name="M2")
        p3 = create_process(client=other, assigned_lawyer=self.lawyer_a, actor=self.lawyer_a)
        Process.objects.filter(pk=p3.pk).update(current_step=3)
        self.client.force_authenticate(self.lawyer_a)
        resp = self.client.get(reverse("process-list"), {"current_step": 3})
        ids = [row["id"] for row in resp.data["results"]]
        self.assertIn(p3.id, ids)
        self.assertNotIn(p1.id, ids)

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

    def test_update_without_version_is_rejected(self):
        # Omitting the optimistic-lock token must 400, not silently skip the lock.
        process = create_process(
            client=self.client_row, assigned_lawyer=self.lawyer_a, actor=self.lawyer_a
        )
        self.client.force_authenticate(self.lawyer_a)
        resp = self.client.patch(
            reverse("process-detail", args=[process.id]),
            {"lawyer_notes": "no version"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_a_version_that_is_not_a_number_is_a_400_not_a_500(self):
        """Bad input is the client's fault, and must read as such (It.8).

        `int(expected_version)` raised ValueError, which DRF does not translate — so a malformed
        field came back as a server error, and with DEBUG on that answer carries a stack trace.
        """
        process = create_process(
            client=self.client_row, assigned_lawyer=self.lawyer_a, actor=self.lawyer_a
        )
        self.client.force_authenticate(self.lawyer_a)
        resp = self.client.patch(
            reverse("process-detail", args=[process.id]),
            {"lawyer_notes": "x", "version": "not-a-number"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("version", resp.data)

    def _reassign(self, process, lawyer, version=None):
        return self.client.post(
            reverse("process-reassign", args=[process.id]),
            {"assigned_lawyer": lawyer.id, "version": process.version if version is None else version},
            format="json",
        )

    def test_an_admin_can_hand_a_case_to_another_lawyer(self):
        """Assignment is open at creation (2026-08-06), so a mistyped name has to be fixable —
        without this the wrong lawyer owned the case for good and the right one could never edit
        it, since `assigned_lawyer` is on no update serializer."""
        process = create_process(
            client=self.client_row, assigned_lawyer=self.lawyer_a, actor=self.lawyer_a
        )
        self.client.force_authenticate(self.admin)
        resp = self._reassign(process, self.lawyer_b)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        process.refresh_from_db()
        self.assertEqual(process.assigned_lawyer_id, self.lawyer_b.id)

    def test_reassignment_is_audited_with_both_names(self):
        process = create_process(
            client=self.client_row, assigned_lawyer=self.lawyer_a, actor=self.lawyer_a
        )
        self.client.force_authenticate(self.admin)
        self._reassign(process, self.lawyer_b)

        entry = ActivityLog.objects.filter(entity_type="Process", entity_id=str(process.id)).latest("id")
        self.assertEqual(entry.before["assigned_lawyer"], self.lawyer_a.username)
        self.assertEqual(entry.after["assigned_lawyer"], self.lawyer_b.username)
        self.assertEqual(entry.actor_id, self.admin.id)

    def test_a_lawyer_cannot_reassign_even_their_own_case(self):
        """It moves work between people, so it is an admin decision like the duplicate override."""
        process = create_process(
            client=self.client_row, assigned_lawyer=self.lawyer_a, actor=self.lawyer_a
        )
        self.client.force_authenticate(self.lawyer_a)
        self.assertEqual(self._reassign(process, self.lawyer_b).status_code, status.HTTP_403_FORBIDDEN)

    def test_reassignment_enforces_the_optimistic_lock(self):
        process = create_process(
            client=self.client_row, assigned_lawyer=self.lawyer_a, actor=self.lawyer_a
        )
        self.client.force_authenticate(self.admin)
        self.assertEqual(
            self._reassign(process, self.lawyer_b, version=process.version + 5).status_code,
            status.HTTP_409_CONFLICT,
        )

    def test_a_case_cannot_be_handed_to_a_lawyer_who_has_left(self):
        process = create_process(
            client=self.client_row, assigned_lawyer=self.lawyer_a, actor=self.lawyer_a
        )
        self.lawyer_b.is_deleted = True
        self.lawyer_b.save(update_fields=["is_deleted"])
        self.client.force_authenticate(self.admin)
        self.assertEqual(
            self._reassign(process, self.lawyer_b).status_code, status.HTTP_400_BAD_REQUEST
        )

    def test_override_duplicate_is_admin_only(self):
        process = create_process(
            client=self.client_row, assigned_lawyer=self.lawyer_a, actor=self.lawyer_a
        )
        process.duplicate_flagged = True  # simulate a fired warning; override is what's under test
        process.save(update_fields=["duplicate_flagged"])
        url = reverse("process-override-duplicate", args=[process.id])
        body = {"match_reason": "mother_name", "reason": "sibling", "version": process.version}

        self.client.force_authenticate(self.lawyer_a)
        self.assertEqual(self.client.post(url, body, format="json").status_code, 403)

        self.client.force_authenticate(self.admin)
        resp = self.client.post(url, body, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        process.refresh_from_db()
        self.assertFalse(process.duplicate_flagged)

    def test_override_duplicate_enforces_the_optimistic_lock(self):
        # The admin duplicate override sits on top of the "no land twice" guarantee — it must not
        # be reachable without a version token, and must 409 on a stale one (§4.1, §5.7).
        process = create_process(
            client=self.client_row, assigned_lawyer=self.lawyer_a, actor=self.lawyer_a
        )
        process.duplicate_flagged = True
        process.save(update_fields=["duplicate_flagged"])
        url = reverse("process-override-duplicate", args=[process.id])
        self.client.force_authenticate(self.admin)

        no_version = self.client.post(
            url, {"match_reason": "mother_name", "reason": "r"}, format="json"
        )
        self.assertEqual(no_version.status_code, status.HTTP_400_BAD_REQUEST)

        stale = self.client.post(
            url,
            {"match_reason": "mother_name", "reason": "r", "version": process.version + 5},
            format="json",
        )
        self.assertEqual(stale.status_code, status.HTTP_409_CONFLICT)
        process.refresh_from_db()
        self.assertTrue(process.duplicate_flagged)  # neither attempt cleared the flag
