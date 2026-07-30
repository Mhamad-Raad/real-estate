"""Category delete protection — soft-delete must not orphan live records (§11).

`on_delete=PROTECT` is the database's guard against removing a referenced row, but it only fires
on a real SQL `DELETE`. Every delete in this system is a **soft** delete, so the database never
sees one and the guard never runs. These tests pin the application-level replacement.
"""

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from clients.factories import make_client
from common.models import ActivityLog
from processes.services import create_process

from .models import Category


class CategoryDeleteProtectionTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user("adm", password="pw12345678", role=User.Role.ADMIN)
        self.lawyer = User.objects.create_user("lw", password="pw12345678")
        self.category = Category.objects.create(code="A", name="Category A")
        self.client.force_authenticate(self.admin)

    def _delete(self):
        return self.client.delete(reverse("category-detail", args=[self.category.id]))

    def test_unused_category_can_be_deleted(self):
        self.assertEqual(self._delete().status_code, status.HTTP_204_NO_CONTENT)
        self.category.refresh_from_db()
        self.assertTrue(self.category.is_deleted)

    def test_category_with_a_live_process_cannot_be_deleted(self):
        client_row = make_client(full_name="A", pid="199001011234", category=self.category)
        create_process(
            client=client_row,
            assigned_lawyer=self.lawyer,
            actor=self.admin,
            category=self.category,
        )

        resp = self._delete()

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("processes", resp.data["in_use"])
        self.category.refresh_from_db()
        self.assertFalse(self.category.is_deleted)

    def test_category_with_only_a_live_client_cannot_be_deleted(self):
        """A beneficiary alone is enough — the category names their document folder (§6.7)."""
        make_client(full_name="B", pid="199001011235", category=self.category)

        resp = self._delete()

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("clients", resp.data["in_use"])

    def test_category_is_free_once_its_records_are_themselves_deleted(self):
        """The guard counts through the default manager, so it sees live rows only — otherwise a
        category could never be retired after its cases were cleaned up."""
        client_row = make_client(full_name="C", pid="199001011236", category=self.category)
        process = create_process(
            client=client_row,
            assigned_lawyer=self.lawyer,
            actor=self.admin,
            category=self.category,
        )
        process.is_deleted = True
        process.save(update_fields=["is_deleted"])
        client_row.is_deleted = True
        client_row.save(update_fields=["is_deleted"])

        self.assertEqual(self._delete().status_code, status.HTTP_204_NO_CONTENT)

    def test_the_refusal_leaves_no_delete_audit_row(self):
        """A rejected delete must not look like it happened in the audit trail (§11)."""
        make_client(full_name="D", pid="199001011237", category=self.category)
        self._delete()
        self.assertFalse(
            ActivityLog.objects.filter(
                entity_type="Category",
                entity_id=str(self.category.id),
                action=ActivityLog.Action.DELETE,
            ).exists()
        )
