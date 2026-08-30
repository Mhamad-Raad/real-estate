"""Client dedup, soft-delete, and audit invariants (§3.7, §5.7, §11)."""

from datetime import date

from django.db import IntegrityError, transaction
from django.test import TestCase

from accounts.models import User
from common.models import ActivityLog

from .models import Client
from .selectors import duplicate_matches
from .serializers import ClientSerializer
from .services import create_client
from .factories import client_data, make_client


class ClientIdentityTests(TestCase):
    def test_pid_partial_unique_blocks_second_active_client(self):
        make_client(full_name="Sara", pid="199001011234", mother_full_name="Amina")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                make_client(
                    full_name="Sara Dup", pid="199001011234", mother_full_name="Other"
                )

    def test_soft_deleted_pid_can_be_reused(self):
        first = make_client(full_name="Sara", pid="P1", mother_full_name="Amina")
        first.is_deleted = True
        first.save(update_fields=["is_deleted"])
        # Partial index excludes deleted rows, so the same PID is free again.
        second = make_client(full_name="Sara Again", pid="P1", mother_full_name="Amina")
        self.assertNotEqual(first.id, second.id)

    def test_active_manager_hides_soft_deleted(self):
        c = make_client(full_name="Ghost", pid="P9", mother_full_name="M")
        c.is_deleted = True
        c.save(update_fields=["is_deleted"])
        self.assertEqual(Client.objects.count(), 0)
        self.assertEqual(Client.all_objects.count(), 1)


class DuplicateDetectionTests(TestCase):
    def setUp(self):
        self.existing = make_client(
            full_name="Karwan Ali", pid="111", mother_full_name="Nasrin Hassan Mahmoud"
        )

    def test_pid_exact_match_detected(self):
        report = duplicate_matches(pid="111", mother_full_name="Totally Different Name")
        self.assertEqual([c.id for c in report.pid], [self.existing.id])
        self.assertEqual(report.mother_name, [])

    def test_mother_name_flags_sibling_with_different_pid(self):
        # Same mother, different person/PID — the common false positive (§5.7).
        report = duplicate_matches(pid="222", mother_full_name="Nasrin Hassan Mahmoud")
        self.assertEqual(report.pid, [])
        self.assertIn(self.existing.id, [c.id for c in report.mother_name])

    def test_unrelated_person_is_not_flagged(self):
        report = duplicate_matches(pid="999", mother_full_name="Shirin Qadir Rashid")
        self.assertEqual(report.pid, [])
        self.assertEqual(report.mother_name, [])

    def test_partial_overlap_stays_below_the_threshold(self):
        # Sharing one common given name is not a duplicate signal. Postgres' 0.3 default let
        # pairs like this through constantly on Kurdish/Arabic names; 0.5 does not.
        report = duplicate_matches(pid="333", mother_full_name="Nasrin Omar Salih")
        self.assertEqual(report.mother_name, [])


class HouseholdDuplicateTests(TestCase):
    """A married couple is one household and may be allocated land once (§3.7, §5.7).

    Neither direction is reachable by `ix_client_pid_active`, which only knows the `pid` column —
    "no row's `pid` may equal any other row's `spouse_pid`" is a cross-row condition no unique
    index can express, so this is the one duplicate rule that genuinely lives in the app layer.
    """

    def setUp(self):
        self.beneficiary = make_client(
            full_name="Karwan Ali",
            pid="111",
            mother_full_name="Nasrin Hassan Mahmoud",
            marital_status="married",
            spouse_name="Shirin Omar",
            spouse_mother_full_name="Bahar Ahmad",
            spouse_date_of_birth=date(1992, 4, 1),
            spouse_pid="222",
        )

    def test_the_spouse_of_a_beneficiary_cannot_apply_in_their_own_name(self):
        report = duplicate_matches(pid="222", mother_full_name="Bahar Ahmad")
        self.assertEqual([c.id for c in report.household], [self.beneficiary.id])
        self.assertTrue(report.is_duplicate)
        # Reported apart from a PID hit: their National ID is nothing like the beneficiary's.
        self.assertEqual(report.pid, [])

    def test_an_applicant_whose_spouse_is_already_a_beneficiary_is_caught(self):
        report = duplicate_matches(
            pid="333", mother_full_name="Someone Else", spouse_pid="111"
        )
        self.assertEqual([c.id for c in report.household], [self.beneficiary.id])
        self.assertTrue(report.is_duplicate)

    def test_two_applicants_naming_the_same_spouse_are_caught(self):
        report = duplicate_matches(
            pid="444", mother_full_name="Someone Else", spouse_pid="222"
        )
        self.assertEqual([c.id for c in report.household], [self.beneficiary.id])

    def test_an_unrelated_household_is_not_flagged(self):
        report = duplicate_matches(pid="999", mother_full_name="Nobody", spouse_pid="888")
        self.assertFalse(report.is_duplicate)

    def test_a_client_is_not_matched_against_their_own_record(self):
        report = duplicate_matches(
            pid="111",
            mother_full_name="Nasrin Hassan Mahmoud",
            spouse_pid="222",
            exclude_id=self.beneficiary.id,
        )
        self.assertFalse(report.is_duplicate)

    def test_each_conflicting_person_is_reported_once(self):
        """One record can match on both counts; the lawyer should see one name, not two."""
        report = duplicate_matches(
            pid="222", mother_full_name="Bahar Ahmad", spouse_pid="111"
        )
        self.assertEqual(len(report.household), 1)

    def test_a_divorce_clears_the_key_so_the_former_spouse_is_not_blocked(self):
        """Left behind, `spouse_pid` would bar a former spouse from an application they are
        entitled to make — the serializer clears it with the rest of the spouse details."""
        serializer = ClientSerializer(
            instance=self.beneficiary, data={"marital_status": "divorced"}, partial=True
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        self.beneficiary.refresh_from_db()
        self.assertEqual(self.beneficiary.spouse_pid, "")
        report = duplicate_matches(pid="222", mother_full_name="Bahar Ahmad")
        self.assertFalse(report.is_duplicate)


class ClientServiceTests(TestCase):
    def test_create_client_writes_audit(self):
        actor = User.objects.create_user(username="lw", password="pw12345678")
        client = create_client(
            data=client_data(full_name="Nma", pid="555", mother_full_name="Bahar"),
            actor=actor,
        )
        self.assertTrue(
            ActivityLog.objects.filter(
                action=ActivityLog.Action.CREATE,
                entity_type="Client",
                entity_id=str(client.id),
            ).exists()
        )


class SpouseDetailConstraintTests(TestCase):
    """The DB is the last line: the serializer can be bypassed, a check constraint cannot."""

    def test_married_client_without_spouse_details_is_rejected_by_the_database(self):
        for field in ("spouse_name", "spouse_date_of_birth", "spouse_mother_full_name"):
            with self.subTest(blank=field):
                data = client_data(
                    pid=f"CK-{field}",
                    marital_status=Client.MaritalStatus.MARRIED,
                )
                data[field] = None if field == "spouse_date_of_birth" else ""
                with self.assertRaises(IntegrityError):
                    with transaction.atomic():
                        Client.objects.create(**data)

    def test_unmarried_client_with_blank_spouse_details_is_fine(self):
        client = make_client(pid="CK-single", marital_status=Client.MaritalStatus.SINGLE)

        self.assertEqual(client.spouse_name, "")
