"""Invariant tests for the shared base models and audit service (§3.1, §11)."""

from django.core.management.base import CommandError
from django.db import ProgrammingError, transaction
from django.test import TestCase, TransactionTestCase
from django.urls import NoReverseMatch, reverse

from accounts.models import User

from .management.scratch_db import require_scratch_database
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


class AppendOnlyAuditTests(TransactionTestCase):
    """The database itself must refuse to alter `activity_log` (§11, §12, migration common/0003).

    Not a `TestCase`: the trigger raises, which aborts the surrounding transaction, and an
    atomic-wrapped test cannot continue afterwards to assert the row survived.
    """

    def _log(self):
        return record_activity(
            actor=None, action=ActivityLog.Action.LOGIN, entity_type="User", entity_id=1
        )

    def test_update_is_rejected(self):
        log = self._log()
        with self.assertRaises(ProgrammingError):
            with transaction.atomic():
                ActivityLog.objects.filter(pk=log.pk).update(entity_type="Tampered")
        self.assertEqual(ActivityLog.objects.get(pk=log.pk).entity_type, "User")

    def test_delete_is_rejected(self):
        log = self._log()
        with self.assertRaises(ProgrammingError):
            with transaction.atomic():
                ActivityLog.objects.filter(pk=log.pk).delete()
        self.assertTrue(ActivityLog.objects.filter(pk=log.pk).exists())

    def test_insert_still_works(self):
        self.assertIsNotNone(self._log().pk)


class ScratchDatabaseGuardTests(TestCase):
    """The perf commands must not write to a database that could hold real records (§13.1)."""

    def test_scratch_name_passes(self):
        require_scratch_database("landalloc_scale", confirmed=False)

    def test_real_name_is_refused(self):
        with self.assertRaises(CommandError):
            require_scratch_database("landalloc", confirmed=False)

    def test_explicit_confirmation_overrides(self):
        require_scratch_database("landalloc", confirmed=True)
