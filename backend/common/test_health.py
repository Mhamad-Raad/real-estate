"""`/health/` is a readiness check, not a liveness one (§4.2, §13.3).

It answered a static `{"status": "ok"}` until It.9 — true the instant Django started, so a Compose
healthcheck or a restore drill that trusted it learned nothing. **A health endpoint that cannot
fail is worse than none**, because it is believed. These tests exist to keep it able to fail.
"""

import tempfile
from pathlib import Path
from unittest import mock

from django.test import Client, TestCase, override_settings


class HealthTests(TestCase):
    def _get(self):
        response = Client().get("/api/v1/health/")
        return response, response.json()

    def test_it_reports_every_dependency_it_claims_to_check(self):
        _, body = self._get()

        self.assertEqual(set(body["checks"]), {"database", "redis", "documents"})

    def test_a_healthy_instance_is_200_and_ok(self):
        response, body = self._get()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["status"], "ok")

    def test_it_carries_the_build_so_a_support_call_can_ask_the_server(self):
        _, body = self._get()

        self.assertIn("app_version", body)
        self.assertIn("build", body)

    def test_a_broken_database_makes_it_503(self):
        """The check that matters after a restore: the app is up, but is its data there?"""
        with mock.patch("django.db.connection.cursor", side_effect=RuntimeError("gone")):
            response, body = self._get()

        self.assertEqual(response.status_code, 503)
        self.assertEqual(body["status"], "degraded")
        self.assertTrue(body["checks"]["database"].startswith("error"))

    def test_an_unreachable_broker_makes_it_503(self):
        """Without Redis a generation is accepted and then never runs — a job stuck for ever."""
        with override_settings(CELERY_BROKER_URL="redis://127.0.0.1:6399/0"):
            response, body = self._get()

        self.assertEqual(response.status_code, 503)
        self.assertTrue(body["checks"]["redis"].startswith("error"))

    def test_an_unwritable_document_store_makes_it_503(self):
        """A bind mount can be present and read-only, which fails at the first upload rather than
        at start-up — unless this probe actually *writes*.

        The failure is injected rather than made with `chmod`: these containers run as **root**,
        and root ignores permission bits, so a `0o500` directory would still be writable and the
        test would pass while proving nothing. A real `:ro` mount fails for root too, which is the
        case this stands in for.
        """
        with mock.patch.object(Path, "write_text", side_effect=OSError("read-only file system")):
            response, body = self._get()

        self.assertEqual(response.status_code, 503)
        self.assertTrue(body["checks"]["documents"].startswith("error"))

    def test_the_write_probe_leaves_nothing_behind(self):
        """It runs on every Compose healthcheck — a stray file each time would litter the store."""
        store = Path(tempfile.mkdtemp()) / "documents"
        with override_settings(DOCUMENTS_ROOT=store):
            self._get()

        self.assertEqual(list(store.iterdir()), [])
