"""Admin Users API — RBAC, soft-delete/restore, self-delete guard, optimistic lock (§4, §7)."""

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from common.models import ActivityLog

from .models import User


class UsersApiTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user("admin_u", password="pw12345678", role=User.Role.ADMIN)
        self.lawyer = User.objects.create_user("lawyer_u", password="pw12345678")

    def test_non_admin_is_forbidden(self):
        self.client.force_authenticate(self.lawyer)
        self.assertEqual(self.client.get(reverse("user-list")).status_code, 403)

    def test_assignable_lawyers_list_is_open_to_any_authed_user(self):
        # Non-admins need this for per-institute assignment dropdowns (§5.1).
        self.client.force_authenticate(self.lawyer)
        resp = self.client.get(reverse("lawyers"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        usernames = [u["username"] for u in resp.data]
        self.assertIn("admin_u", usernames)
        self.assertIn("lawyer_u", usernames)
        self.assertEqual(set(resp.data[0].keys()), {"id", "username"})  # minimal shape only

    def test_admin_creates_user_with_hashed_password(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post(
            reverse("user-list"),
            {"username": "new_lawyer", "password": "sup3rSecret!", "role": "lawyer"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertNotIn("password", resp.data)  # never echoed back
        created = User.objects.get(username="new_lawyer")
        self.assertTrue(created.check_password("sup3rSecret!"))  # stored hashed, verifiable
        self.assertTrue(
            ActivityLog.objects.filter(
                action=ActivityLog.Action.CREATE, entity_type="User", entity_id=str(created.id)
            ).exists()
        )

    def test_soft_delete_hides_and_deactivates(self):
        target = User.objects.create_user("victim", password="pw12345678")
        self.client.force_authenticate(self.admin)
        resp = self.client.delete(reverse("user-detail", args=[target.id]))
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        target.refresh_from_db()
        self.assertTrue(target.is_deleted)
        self.assertFalse(target.is_active)  # can no longer authenticate
        # Hidden from the default list.
        listing = self.client.get(reverse("user-list"))
        self.assertNotIn(target.id, [u["id"] for u in listing.data["results"]])

    def test_admin_cannot_delete_self(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.delete(reverse("user-detail", args=[self.admin.id]))
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.admin.refresh_from_db()
        self.assertFalse(self.admin.is_deleted)

    def test_restore_reactivates(self):
        target = User.objects.create_user("comeback", password="pw12345678", is_active=False)
        target.is_deleted = True
        target.save(update_fields=["is_deleted"])
        self.client.force_authenticate(self.admin)
        resp = self.client.post(reverse("user-restore", args=[target.id]))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        target.refresh_from_db()
        self.assertFalse(target.is_deleted)
        self.assertTrue(target.is_active)

    def test_cannot_demote_the_last_admin(self):
        # self.admin is the only admin — demoting to lawyer would lock everyone out.
        self.client.force_authenticate(self.admin)
        resp = self.client.patch(
            reverse("user-detail", args=[self.admin.id]),
            {"role": "lawyer", "version": self.admin.version},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.role, User.Role.ADMIN)

    def test_cannot_deactivate_the_last_admin(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.patch(
            reverse("user-detail", args=[self.admin.id]),
            {"is_active": False, "version": self.admin.version},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_can_demote_an_admin_when_another_remains(self):
        other_admin = User.objects.create_user("admin_b", password="pw12345678", role=User.Role.ADMIN)
        self.client.force_authenticate(self.admin)
        resp = self.client.patch(
            reverse("user-detail", args=[other_admin.id]),
            {"role": "lawyer", "version": other_admin.version},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        other_admin.refresh_from_db()
        self.assertEqual(other_admin.role, User.Role.LAWYER)

    def test_update_requires_version_and_rejects_stale(self):
        target = User.objects.create_user("editme", password="pw12345678")
        self.client.force_authenticate(self.admin)
        url = reverse("user-detail", args=[target.id])
        # Missing version → 400 (lock can't be silently skipped).
        self.assertEqual(
            self.client.patch(url, {"first_name": "No Version"}, format="json").status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        # Correct version → 200 and bumps to 2.
        ok = self.client.patch(url, {"first_name": "A", "version": 1}, format="json")
        self.assertEqual(ok.status_code, status.HTTP_200_OK)
        # Re-using the now-stale version → 409.
        stale = self.client.patch(url, {"first_name": "B", "version": 1}, format="json")
        self.assertEqual(stale.status_code, status.HTTP_409_CONFLICT)
