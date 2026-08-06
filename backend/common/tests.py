"""Invariant tests for the shared base models and audit service (§3.1, §11)."""

from django.test import TestCase
from django.urls import NoReverseMatch, reverse

from accounts.models import User

from .models import ActivityLog
from .services import record_activity


class NoSecondWritePathTests(TestCase):
    """Django's admin site must stay unmounted (It.8).

    It was scaffolded in It.0 with ModelAdmins for Client, Process, Document, Category and User.
    Probed before removal: a staff account hard-deleted a `Document` row through it — gone from
    `all_objects` — and wrote **no** audit row. Soft-delete-only and the append-only trail are
    the system's first invariants (§11.1, §11.2), and they are only worth as much as the number
    of write paths that honour them, so this pins the count at one.
    """

    def test_the_admin_site_is_not_routable(self):
        for name in ("admin:index", "admin:clients_client_delete"):
            with self.assertRaises(NoReverseMatch):
                reverse(name)
        self.assertEqual(self.client.get("/admin/").status_code, 404)

    def test_no_app_registers_a_model_admin(self):
        from django.apps import apps

        self.assertFalse(
            apps.is_installed("django.contrib.admin"),
            "django.contrib.admin is installed again — it writes outside the service layer.",
        )


class AuditServiceTests(TestCase):
    def test_record_activity_appends_row_with_before_after(self):
        actor = User.objects.create_user(username="a", password="pw12345678")
        log = record_activity(
            actor=actor,
            action=ActivityLog.Action.UPDATE,
            entity_type="Process",
            entity_id=42,
            before={"status": "draft"},
            after={"status": "active"},
            ip_address="10.0.0.5",
        )
        self.assertEqual(log.entity_id, "42")
        self.assertEqual(log.before["status"], "draft")
        self.assertEqual(log.after["status"], "active")
        self.assertEqual(log.ip_address, "10.0.0.5")

    def test_anonymous_actor_stored_as_null(self):
        class Anon:
            is_authenticated = False

        log = record_activity(
            actor=Anon(),
            action=ActivityLog.Action.LOGIN,
            entity_type="User",
        )
        self.assertIsNone(log.actor)
