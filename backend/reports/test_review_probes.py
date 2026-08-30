"""Review probes for the It.7 batch — run in the test DB, never the dev shell."""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from catalog.models import Category
from clients.factories import make_client
from common.models import ActivityLog
from common.services import record_activity
from processes.models import Process
from processes.services import create_process

from .selectors import dashboard_stats, user_report


class UserReportShapeTests(TestCase):
    """The rewrite annotates one relation three times — the classic double-count trap."""

    def setUp(self):
        self.category = Category.objects.create(code="PR", name="Probe")
        self.lawyer = User.objects.create_user("probe_lw", password="pw12345678")

    def test_three_filtered_counts_over_one_relation_do_not_multiply(self):
        for i, status in enumerate(
            ["complete", "complete", "in_progress", "in_progress", "draft"]
        ):
            process = create_process(
                client=make_client(full_name=f"P{i}", pid=f"PRB-{i}"),
                assigned_lawyer=self.lawyer,
                actor=self.lawyer,
                category=self.category,
            )
            Process.objects.filter(pk=process.pk).update(overall_status=status)

        row = {r["username"]: r for r in user_report()}["probe_lw"]

        self.assertEqual((row["assigned"], row["completed"], row["in_progress"]), (5, 2, 2))

    def test_a_soft_deleted_case_is_not_counted(self):
        process = create_process(
            client=make_client(pid="PRB-DEL"),
            assigned_lawyer=self.lawyer,
            actor=self.lawyer,
        )
        Process.objects.filter(pk=process.pk).update(is_deleted=True)

        row = {r["username"]: r for r in user_report()}["probe_lw"]

        self.assertEqual(row["assigned"], 0)


class HandledSemanticsTests(TestCase):
    """`by_lawyer_handled` reads the audit log, which outlives the rows it describes."""

    def setUp(self):
        self.lawyer = User.objects.create_user("handled_lw", password="pw12345678")

    def test_work_on_a_case_that_was_later_deleted_still_counts_as_work(self):
        """Deliberate: the audit log records what a person did, and deleting the case does not
        un-do their day. Pinned so the semantics cannot drift silently."""
        process = create_process(
            client=make_client(pid="HND-1"), assigned_lawyer=self.lawyer, actor=self.lawyer
        )
        record_activity(
            actor=self.lawyer,
            action=ActivityLog.Action.UPDATE,
            entity_type="Process",
            entity_id=process.id,
            after={"land_id": "L"},
        )
        Process.objects.filter(pk=process.pk).update(is_deleted=True)

        rows = {r["username"]: r["count"] for r in dashboard_stats()["by_lawyer_handled"]}

        self.assertEqual(rows["handled_lw"], 1)

    def test_a_deactivated_user_still_appears_in_handled(self):
        """The opposite of the report: someone who left still did the work that month."""
        process = create_process(
            client=make_client(pid="HND-2"), assigned_lawyer=self.lawyer, actor=self.lawyer
        )
        record_activity(
            actor=self.lawyer,
            action=ActivityLog.Action.UPDATE,
            entity_type="Process",
            entity_id=process.id,
            after={},
        )
        User.objects.filter(pk=self.lawyer.pk).update(is_active=False)

        rows = {r["username"]: r["count"] for r in dashboard_stats()["by_lawyer_handled"]}

        self.assertIn("handled_lw", rows)


class WindowBoundaryTests(TestCase):
    """The previous-period figures must not overlap the current window or double-count."""

    def setUp(self):
        self.lawyer = User.objects.create_user("win_lw", password="pw12345678")

    def _case(self, pid, *, days_ago):
        process = create_process(
            client=make_client(pid=pid), assigned_lawyer=self.lawyer, actor=self.lawyer
        )
        when = timezone.now() - timedelta(days=days_ago)
        Process.objects.filter(pk=process.pk).update(created_at=when)
        from clients.models import Client

        Client.objects.filter(pk=process.client_id).update(created_at=when)
        return process

    def test_current_and_previous_windows_are_disjoint(self):
        self._case("WIN-1", days_ago=5)  # current
        self._case("WIN-2", days_ago=40)  # previous
        self._case("WIN-3", days_ago=200)  # neither

        stats = dashboard_stats()

        self.assertEqual(stats["processes_in_window"], 1)
        self.assertEqual(stats["processes_previous"], 1)
        self.assertEqual(stats["clients_in_window"], 1)
        self.assertEqual(stats["clients_previous"], 1)
