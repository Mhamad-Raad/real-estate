"""Client dedup, soft-delete, and audit invariants (§3.7, §5.7, §11)."""

from django.db import IntegrityError, transaction
from django.test import TestCase

from accounts.models import User
from common.models import ActivityLog

from .models import Client
from .selectors import duplicate_matches
from .services import create_client


class ClientIdentityTests(TestCase):
    def test_pid_partial_unique_blocks_second_active_client(self):
        Client.objects.create(full_name="Sara", pid="199001011234", mother_full_name="Amina")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Client.objects.create(
                    full_name="Sara Dup", pid="199001011234", mother_full_name="Other"
                )

    def test_soft_deleted_pid_can_be_reused(self):
        first = Client.objects.create(full_name="Sara", pid="P1", mother_full_name="Amina")
        first.is_deleted = True
        first.save(update_fields=["is_deleted"])
        # Partial index excludes deleted rows, so the same PID is free again.
        second = Client.objects.create(full_name="Sara Again", pid="P1", mother_full_name="Amina")
        self.assertNotEqual(first.id, second.id)

    def test_active_manager_hides_soft_deleted(self):
        c = Client.objects.create(full_name="Ghost", pid="P9", mother_full_name="M")
        c.is_deleted = True
        c.save(update_fields=["is_deleted"])
        self.assertEqual(Client.objects.count(), 0)
        self.assertEqual(Client.all_objects.count(), 1)


class DuplicateDetectionTests(TestCase):
    def setUp(self):
        self.existing = Client.objects.create(
            full_name="Karwan Ali", pid="111", mother_full_name="Nasrin Hassan Mahmoud"
        )

    def test_pid_exact_match_detected(self):
        pid_matches, mother_matches = duplicate_matches(
            pid="111", mother_full_name="Totally Different Name"
        )
        self.assertEqual([c.id for c in pid_matches], [self.existing.id])
        self.assertEqual(mother_matches, [])

    def test_mother_name_flags_sibling_with_different_pid(self):
        # Same mother, different person/PID — the common false positive (§5.7).
        pid_matches, mother_matches = duplicate_matches(
            pid="222", mother_full_name="Nasrin Hassan Mahmoud"
        )
        self.assertEqual(pid_matches, [])
        self.assertIn(self.existing.id, [c.id for c in mother_matches])

    def test_unrelated_person_is_not_flagged(self):
        pid_matches, mother_matches = duplicate_matches(
            pid="999", mother_full_name="Shirin Qadir Rashid"
        )
        self.assertEqual(pid_matches, [])
        self.assertEqual(mother_matches, [])


class ClientServiceTests(TestCase):
    def test_create_client_writes_audit(self):
        actor = User.objects.create_user(username="lw", password="pw12345678")
        client = create_client(
            data={"full_name": "Nma", "pid": "555", "mother_full_name": "Bahar"},
            actor=actor,
        )
        self.assertTrue(
            ActivityLog.objects.filter(
                action=ActivityLog.Action.CREATE,
                entity_type="Client",
                entity_id=str(client.id),
            ).exists()
        )
