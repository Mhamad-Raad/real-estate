"""Invariant tests for the shared base models and audit service (§3.1, §11)."""

from django.test import TestCase

from accounts.models import User

from .models import ActivityLog
from .services import record_activity


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
