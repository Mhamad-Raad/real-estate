"""Review probes for batches 16–17 (2026-08-04). Each must fail before it is claimed."""

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from catalog.models import Category
from clients.factories import make_client

from .models import Process, ProcessStep
from .services import create_process
from .status import compute_step_status


class ReapplyKeepsItsPlaceTests(APITestCase):
    """A rejected applicant may re-apply (UC-028). The new case must be a real case."""

    def setUp(self):
        self.lawyer = User.objects.create_user("re_lw", password="pw12345678")
        self.category = Category.objects.create(code="A", name="A")
        self.client_row = make_client(pid="197001019999", category=self.category)
        self.process = create_process(
            client=self.client_row,
            assigned_lawyer=self.lawyer,
            actor=self.lawyer,
            category=self.category,
        )
        self.process.overall_status = Process.OverallStatus.REJECTED
        self.process.save(update_fields=["overall_status"])
        self.client.force_authenticate(self.lawyer)

    def test_a_re_applied_case_still_gets_a_category_and_a_code(self):
        """Re-apply posts only `client`, so the new case would inherit neither — and since the
        category is now fixed at creation (UC-059) it could never acquire one afterwards."""
        resp = self.client.post(
            reverse("process-list"), {"client": self.client_row.id}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        fresh = Process.objects.get(pk=resp.data["id"])
        self.assertIsNotNone(fresh.category_id, "the re-applied case has no category")
        self.assertTrue(fresh.unique_code, "the re-applied case has no unique code")


class ProceedLeavesNoStaleStatusTests(APITestCase):
    """Stamping the start date is a change to the step's own data (UC-050)."""

    def setUp(self):
        self.lawyer = User.objects.create_user("adv_lw", password="pw12345678")
        self.category = Category.objects.create(code="A", name="A")
        self.process = create_process(
            client=make_client(pid="197001018888", category=self.category),
            assigned_lawyer=self.lawyer,
            actor=self.lawyer,
            category=self.category,
        )
        self.client.force_authenticate(self.lawyer)

    def test_the_step_opened_by_proceed_has_an_honest_status(self):
        self.process.refresh_from_db()
        resp = self.client.post(
            reverse("process-advance-step", args=[self.process.id]),
            {"version": self.process.version},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        process = Process.objects.prefetch_related(
            "steps", "documents", "institute_entries"
        ).get(pk=self.process.pk)
        row = process.steps.get(step_number=2)
        self.assertEqual(
            row.status,
            compute_step_status(process, 2, row),
            "the step now holds a start date but its stored status was not re-derived",
        )


class DisprovenSuspicionsTests(APITestCase):
    """Things that looked wrong on reading and turned out to be fine. Kept so they are not re-raised."""

    def setUp(self):
        self.lawyer = User.objects.create_user("dis_lw", password="pw12345678")
        self.a = Category.objects.create(code="A", name="A")
        self.client.force_authenticate(self.lawyer)

    def test_allocation_ignores_a_soft_deleted_category(self):
        """`all_objects` is used for the lock — a retired category must still lock, not vanish."""
        self.a.is_deleted = True
        self.a.save(update_fields=["is_deleted"])
        process = create_process(
            client=make_client(pid="197001017777", category=self.a),
            assigned_lawyer=self.lawyer,
            actor=self.lawyer,
            category=self.a,
        )
        self.assertEqual(process.unique_code, "A1")

    def test_a_category_code_containing_a_regex_character_is_safe(self):
        """Codes are free text (max_length 20); allocation must not treat one as a pattern."""
        odd = Category.objects.create(code="A.", name="odd")
        first = create_process(
            client=make_client(pid="197001016666", category=odd),
            assigned_lawyer=self.lawyer, actor=self.lawyer, category=odd,
        )
        self.assertEqual(first.unique_code, "A.1")
        # `A.` must not read `A1` (from category A) as one of its own via a dot-wildcard.
        create_process(
            client=make_client(pid="197001016665", category=self.a),
            assigned_lawyer=self.lawyer, actor=self.lawyer, category=self.a,
        )
        second = create_process(
            client=make_client(pid="197001016664", category=odd),
            assigned_lawyer=self.lawyer, actor=self.lawyer, category=odd,
        )
        self.assertEqual(second.unique_code, "A.2")

    def test_step_1_start_date_survives_the_case_being_re_saved(self):
        process = create_process(
            client=make_client(pid="197001015555", category=self.a),
            assigned_lawyer=self.lawyer, actor=self.lawyer, category=self.a,
        )
        stamped = ProcessStep.objects.get(process=process, step_number=1).start_date
        self.assertIsNotNone(stamped)
        process.refresh_from_db()
        self.client.patch(
            reverse("process-detail", args=[process.id]),
            {"land_id": "L-1", "version": process.version}, format="json",
        )
        self.assertEqual(
            ProcessStep.objects.get(process=process, step_number=1).start_date, stamped
        )
