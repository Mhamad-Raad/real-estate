"""The "no land twice" guarantee + override/audit invariants (§3.7, §5.7, §11).

The critical risk this iteration retires: two office computers cannot both create an active
allocation for the same client, even racing. That's enforced by the DB partial-unique index
`ix_process_active_alloc`, exercised below with a real two-connection concurrent insert.
"""

import threading

from django.db import IntegrityError, connections, transaction
from django.test import TestCase, TransactionTestCase

from accounts.models import User
from clients.models import Client
from common.models import ActivityLog

from .models import DuplicateOverride, Process, ProcessStep
from .services import create_process, override_duplicate, recompute_step
from .status import missing_requirements
from clients.factories import make_client


def _make_client(pid="111"):
    return make_client(full_name="Beneficiary", pid=pid, mother_full_name="Mother")


class NoLandTwiceTests(TestCase):
    def setUp(self):
        self.lawyer = User.objects.create_user(username="lw1", password="pw12345678")
        self.client_row = _make_client()

    def _new_process(self, **kwargs):
        return create_process(
            client=self.client_row, assigned_lawyer=self.lawyer, actor=self.lawyer, **kwargs
        )

    def test_second_active_allocation_blocked(self):
        self._new_process()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Process.objects.create(client=self.client_row, assigned_lawyer=self.lawyer)

    def test_rejected_allocation_does_not_block_a_new_one(self):
        first = self._new_process()
        first.overall_status = Process.OverallStatus.REJECTED
        first.save(update_fields=["overall_status"])
        # A rejected case frees the slot — a fresh allocation is allowed.
        second = self._new_process()
        self.assertNotEqual(first.id, second.id)

    def test_soft_deleted_allocation_does_not_block(self):
        first = self._new_process()
        first.is_deleted = True
        first.save(update_fields=["is_deleted"])
        second = self._new_process()
        self.assertNotEqual(first.id, second.id)

    def test_different_clients_each_get_an_allocation(self):
        self._new_process()
        other = _make_client(pid="222")
        p = create_process(client=other, assigned_lawyer=self.lawyer, actor=self.lawyer)
        self.assertEqual(p.client_id, other.id)

    def test_similar_mother_name_is_advisory_and_never_blocks(self):
        # A sibling (same mother, different PID) is flagged for a human glance — but identity is
        # the government PID, so this must not raise the blocking duplicate flag.
        make_client(full_name="Sibling", pid="999", mother_full_name="Mother")
        flagged = self._new_process()
        self.assertTrue(flagged.similar_name_flagged)
        self.assertFalse(flagged.duplicate_flagged)

    def test_similar_name_does_not_gate_step_one(self):
        """The regression this split exists to prevent: a sibling stalling a legitimate case.

        Creation tells the lawyer a mother-name hit is a sibling and lets them proceed; Step 1
        used to then refuse to complete until an admin overrode it.
        """
        make_client(full_name="Sibling", pid="999", mother_full_name="Mother")
        process = self._new_process()
        step = process.steps.get(step_number=1)
        self.assertNotIn("duplicate_flag", missing_requirements(process, 1, step))

    def test_recompute_reaches_a_soft_deleted_process(self):
        """Guards the trap that broke migration 0006: `objects` is ActiveManager.

        Anything sweeping over historical rows must use `all_objects`, or a soft-deleted row
        that the sweep selected raises DoesNotExist when it is re-fetched.
        """
        process = self._new_process()
        Process.all_objects.filter(pk=process.pk).update(is_deleted=True)

        self.assertFalse(Process.objects.filter(pk=process.pk).exists())
        found = Process.all_objects.get(pk=process.pk)
        self.assertEqual(recompute_step(found, 1).step_number, 1)

    def test_no_flags_for_a_clean_client(self):
        clean = _make_client(pid="555")
        clean.mother_full_name = "Farida Ahmed"  # no trigram overlap with the setUp client's "Mother"
        clean.save(update_fields=["mother_full_name"])
        process = create_process(client=clean, assigned_lawyer=self.lawyer, actor=self.lawyer)
        self.assertFalse(process.duplicate_flagged)
        self.assertFalse(process.similar_name_flagged)

    def test_shared_given_name_stays_below_the_threshold(self):
        # Two mothers sharing only a common first name score 0.21 — over Postgres' 0.3 default
        # once other names overlap, but never over 0.5. This is the false-flag case in real data.
        subject = make_client(
            full_name="Karwan Ali", pid="661", mother_full_name="Nasrin Hassan Mahmoud"
        )
        make_client(full_name="Unrelated", pid="662", mother_full_name="Nasrin Omar Salih")
        process = create_process(client=subject, assigned_lawyer=self.lawyer, actor=self.lawyer)
        self.assertFalse(process.similar_name_flagged)

    def test_create_process_makes_five_steps_and_audits(self):
        process = self._new_process()
        self.assertEqual(
            sorted(ProcessStep.objects.filter(process=process).values_list("step_number", flat=True)),
            [1, 2, 3, 4, 5],
        )
        self.assertTrue(
            ActivityLog.objects.filter(
                action=ActivityLog.Action.CREATE, entity_type="Process", entity_id=str(process.id)
            ).exists()
        )


class DuplicateOverrideTests(TestCase):
    def test_admin_override_clears_flag_and_logs(self):
        admin = User.objects.create_user(username="ad", password="pw12345678", role=User.Role.ADMIN)
        client_row = _make_client(pid="333")
        process = create_process(client=client_row, assigned_lawyer=admin, actor=admin)
        process.duplicate_flagged = True  # simulate a fired warning; override is what's under test
        process.save(update_fields=["duplicate_flagged"])
        override = override_duplicate(
            process=process,
            admin=admin,
            match_reason=DuplicateOverride.MatchReason.MOTHER_NAME,
            reason="Sibling — different PID, legitimately eligible.",
            expected_version=process.version,
        )
        process.refresh_from_db()
        self.assertFalse(process.duplicate_flagged)
        self.assertEqual(process.version, 2)  # optimistic-lock counter bumped
        self.assertEqual(override.overridden_by_id, admin.id)
        self.assertTrue(
            ActivityLog.objects.filter(
                action=ActivityLog.Action.OVERRIDE, entity_id=str(process.id)
            ).exists()
        )


class NoLandTwiceConcurrencyTests(TransactionTestCase):
    """Two connections race to allocate the same client — the DB index must let exactly one win."""

    reset_sequences = True

    def test_concurrent_second_allocation_is_blocked_by_the_db(self):
        lawyer = User.objects.create_user(username="race", password="pw12345678")
        client_row = _make_client(pid="race-1")
        barrier = threading.Barrier(2)
        results = []

        def worker():
            barrier.wait()  # release both threads at the same instant
            try:
                with transaction.atomic():
                    p = Process.objects.create(client=client_row, assigned_lawyer=lawyer)
                    ProcessStep.objects.bulk_create(
                        [ProcessStep(process=p, step_number=n) for n in range(1, 6)]
                    )
                results.append("ok")
            except IntegrityError:
                results.append("blocked")
            finally:
                connections.close_all()

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(sorted(results), ["blocked", "ok"])
        self.assertEqual(
            Process.objects.filter(client=client_row, is_deleted=False).count(), 1
        )
