"""Dashboard + report aggregation and RBAC (§10.1, §10.2)."""

from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import User
from catalog.models import Category
from clients.factories import make_client
from processes.models import Process, ProcessStep
from processes.services import create_process

from .selectors import dashboard_stats, user_report, week_start


class ReportsTestBase(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="adm", password="pw12345678", role=User.Role.ADMIN
        )
        self.lawyer = User.objects.create_user(username="lw", password="pw12345678")
        self.category = Category.objects.create(name="A", code="A")

    def _process(self, pid, *, lawyer=None, status=None):
        client = make_client(full_name=f"P{pid}", pid=pid, mother_full_name=f"M{pid}")
        process = create_process(
            client=client,
            assigned_lawyer=lawyer or self.lawyer,
            actor=self.admin,
            category=self.category,
        )
        if status:
            process.overall_status = status
            process.save(update_fields=["overall_status"])
        return process


class DashboardTests(ReportsTestBase):
    def test_counts_this_week_and_groups_every_bucket(self):
        self._process("101")
        self._process("102", status=Process.OverallStatus.COMPLETE)
        stats = dashboard_stats()

        self.assertEqual(stats["processes_this_week"], 2)
        self.assertEqual(stats["clients_this_week"], 2)
        self.assertEqual(stats["processes_by_status"]["complete"], 1)
        # Every status and step is present even at zero, so a chart never changes shape.
        self.assertEqual(set(stats["processes_by_status"]), set(Process.OverallStatus.values))
        self.assertEqual(set(stats["processes_by_step"]), {"1", "2", "3", "4", "5"})
        self.assertEqual(stats["processes_by_step"]["1"], 2)

    def test_last_week_is_excluded(self):
        old = self._process("103")
        Process.objects.filter(pk=old.pk).update(created_at=week_start() - timedelta(days=1))
        self.assertEqual(dashboard_stats()["processes_this_week"], 0)
        self.assertEqual(dashboard_stats()["processes_total"], 1)

    def test_missing_files_counted_by_step_and_by_case(self):
        process = self._process("104")
        # One case short of files on two steps must count twice by step, once by case.
        process.steps.filter(step_number__in=[1, 2]).update(status=ProcessStep.Status.MISSING)
        stats = dashboard_stats()
        self.assertEqual(stats["steps_missing_files"], 2)
        self.assertEqual(stats["processes_missing_files"], 1)

    def test_advisory_name_flag_is_reported_separately(self):
        process = self._process("105")
        Process.objects.filter(pk=process.pk).update(similar_name_flagged=True)
        stats = dashboard_stats()
        self.assertEqual(stats["similar_name_flagged"], 1)
        self.assertEqual(stats["duplicate_flagged"], 0)

    def test_query_count_does_not_grow_with_data(self):
        """The guard that matters: every figure must stay a GROUP BY, not a loop."""
        self._process("201")
        with self.assertNumQueries(10):
            dashboard_stats()
        for pid in range(202, 212):
            self._process(str(pid))
        with self.assertNumQueries(10):
            dashboard_stats()

    def test_requires_authentication(self):
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 401)

    def test_any_authenticated_user_may_read(self):
        self.client.force_authenticate(self.lawyer)
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)


class ReportsRbacTests(ReportsTestBase):
    def test_reports_are_admin_only(self):
        self.client.force_authenticate(self.lawyer)
        for name in ("report-processes", "report-users"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 403, name)

    def test_admin_may_read_reports(self):
        self.client.force_authenticate(self.admin)
        for name in ("report-processes", "report-users"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)


class ReportFilterTests(ReportsTestBase):
    def test_date_range_filters(self):
        old = self._process("301")
        Process.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=30))
        self._process("302")
        self.client.force_authenticate(self.admin)

        today = timezone.localtime().date()
        response = self.client.get(reverse("report-processes"), {"date_from": today.isoformat()})
        self.assertEqual(response.data["total"], 1)

    def test_bad_date_is_a_400_not_a_500(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get(reverse("report-processes"), {"date_from": "not-a-date"})
        self.assertEqual(response.status_code, 400)

    def test_reversed_range_is_rejected(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get(
            reverse("report-processes"), {"date_from": "2026-05-02", "date_to": "2026-05-01"}
        )
        self.assertEqual(response.status_code, 400)

    def test_user_report_splits_assigned_from_completed(self):
        self._process("401")
        self._process("402", status=Process.OverallStatus.COMPLETE)
        rows = user_report()
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["assigned"], rows[0]["completed"]), (2, 1))

    def test_csv_neutralises_formula_injection(self):
        """A name Excel would execute must be exported as text (§12 input safety)."""
        self.category.name = "=1+1"
        self.category.save(update_fields=["name"])
        self._process("601")
        self.client.force_authenticate(self.admin)

        body = self.client.get(reverse("report-processes"), {"export": "csv"}).content.decode()
        self.assertIn("'=1+1", body)
        self.assertNotIn(",=1+1", body)

    def test_csv_neutralises_a_formula_username(self):
        # Django's username validator permits `+` and `-`, so this reaches the users report.
        lawyer = User.objects.create_user(username="+1+1", password="pw12345678")
        self._process("602", lawyer=lawyer)
        self.client.force_authenticate(self.admin)

        body = self.client.get(reverse("report-users"), {"export": "csv"}).content.decode()
        self.assertIn("'+1+1", body)

    def test_csv_export_is_utf8_with_bom(self):
        self._process("501")
        self.client.force_authenticate(self.admin)
        response = self.client.get(reverse("report-users"), {"export": "csv"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
        self.assertIn("attachment;", response["Content-Disposition"])
        # Without the BOM, Excel on the office's Windows hosts mangles Sorani/Arabic.
        self.assertTrue(response.content.decode("utf-8").startswith("﻿"))
        self.assertIn("lw", response.content.decode("utf-8"))
