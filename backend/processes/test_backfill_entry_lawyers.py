"""UC-105: the institute rows filed before a row inherited its case's lawyer."""

from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from accounts.models import User
from clients.factories import make_client
from common.models import ActivityLog
from processes.models import ProcessInstituteEntry
from processes.services import create_process


class BackfillEntryLawyersTests(TestCase):
    def setUp(self):
        self.lawyer = User.objects.create_user("bf", password="pw12345678")
        self.process = create_process(
            client=make_client(full_name="B", pid="BF-1", mother_full_name="M"),
            assigned_lawyer=self.lawyer,
            actor=self.lawyer,
        )
        self.entry = ProcessInstituteEntry.objects.create(
            process=self.process, step_number=2, institute_code="INST_S2_A"
        )

    def _run(self, *args):
        out = StringIO()
        call_command("backfill_entry_lawyers", *args, stdout=out)
        return out.getvalue()

    def test_it_reports_without_writing_unless_asked(self):
        """It touches live records, so the default has to be "tell me, do not do it"."""
        output = self._run()

        self.entry.refresh_from_db()
        self.assertIn("1 institute row", output)
        self.assertIsNone(self.entry.assigned_lawyer)

    def test_apply_fills_the_blank_from_the_case(self):
        self._run("--apply")

        self.entry.refresh_from_db()
        self.assertEqual(self.entry.assigned_lawyer, self.lawyer)

    def test_it_never_overwrites_a_row_that_names_someone(self):
        """A blank means "nobody wrote it down"; a name means a decision, and this must not touch
        one — an institute genuinely handled by a colleague keeps saying so."""
        other = User.objects.create_user("bf2", password="pw12345678")
        named = ProcessInstituteEntry.objects.create(
            process=self.process, step_number=2, institute_code="INST_S2_B",
            assigned_lawyer=other,
        )

        self._run("--apply")

        named.refresh_from_db()
        self.assertEqual(named.assigned_lawyer, other)

    def test_every_fill_is_audited(self):
        """A field that changes with no trace is a field nobody can explain later (§11)."""
        self._run("--apply")

        entry = ActivityLog.objects.filter(
            entity_type="ProcessInstituteEntry", entity_id=str(self.entry.id)
        ).latest("created_at")
        self.assertIsNone(entry.before["assigned_lawyer"])
        self.assertEqual(entry.after["assigned_lawyer"], self.lawyer.id)

    def test_running_it_twice_does_nothing_the_second_time(self):
        self._run("--apply")

        output = self._run("--apply")

        self.assertIn("Nothing to do", output)
