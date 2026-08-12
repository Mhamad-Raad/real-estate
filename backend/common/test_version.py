"""The build stamp (§2.6): resolution order, graceful degradation, and where it surfaces."""

from __future__ import annotations

import importlib
import os
import tempfile
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from common import version as version_module
from common.testing import broker_reachable
from common.models import ActivityLog
from common.services import record_activity


class VersionResolutionTests(TestCase):
    """Environment wins over the file, and nothing here may raise — an offline office computer
    must start even when the build cannot be resolved."""

    def test_parses_keys_and_ignores_comments_and_blanks(self):
        """Deliberately does NOT read the real repo-root file: inside a container that file does
        not exist (the image is built from `backend/` alone) and the values arrive as environment
        instead. Asserting the file is present would pin the environment, not the parser."""
        original = version_module._VERSION_FILE
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "VERSION"
            path.write_text(
                "# a comment\n\nAPP_VERSION=1.2.3\n  APP_BUILD = 7 \nNOT_A_PAIR\n",
                encoding="utf-8",
            )
            try:
                version_module._VERSION_FILE = path
                values = version_module._read_version_file()
            finally:
                version_module._VERSION_FILE = original
        self.assertEqual(values, {"APP_VERSION": "1.2.3", "APP_BUILD": "7"})

    def test_environment_wins_over_the_file(self):
        """The contract that makes containers work: the image bakes APP_VERSION/APP_BUILD in."""
        with mock.patch.dict(os.environ, {"APP_VERSION": "9.9.9", "APP_BUILD": "77"}):
            reloaded = importlib.reload(version_module)
            try:
                self.assertEqual(reloaded.APP_VERSION, "9.9.9")
                self.assertEqual(reloaded.BUILD_NUMBER, 77)
                self.assertEqual(reloaded.VERSION_STRING, "9.9.9 (build 77)")
            finally:
                importlib.reload(version_module)

    def test_a_malformed_build_degrades_to_unknown_instead_of_raising(self):
        for bad in ("", "  ", "not-a-number", None, "1.2"):
            with self.subTest(bad=bad):
                self.assertEqual(version_module._coerce_build(bad), version_module.UNKNOWN_BUILD)

    def test_a_negative_build_degrades_rather_than_breaking_every_write(self):
        """`ActivityLog.app_build` is a PositiveIntegerField with a DB check constraint, so a
        negative that got past here would fail EVERY audit write — and audit is written inside
        every service transaction. Probed: IntegrityError on `activity_log_app_build_check`."""
        for negative in ("-1", "-999", " -42 "):
            with self.subTest(negative=negative):
                self.assertEqual(
                    version_module._coerce_build(negative), version_module.UNKNOWN_BUILD
                )

    def test_a_negative_env_build_still_lets_audit_write(self):
        """The end-to-end guarantee, not just the helper: a typo'd env var must cost the version
        display and nothing else.

        `common.services` binds `BUILD_NUMBER` **by value** at import, so reloading this module
        alone does not reach the audit writer — patching the name the writer actually reads is
        what makes this exercise `record_activity` instead of merely proving the DB accepts 0.
        """
        with mock.patch.dict(os.environ, {"APP_BUILD": "-1"}):
            reloaded = importlib.reload(version_module)
            try:
                self.assertEqual(reloaded.BUILD_NUMBER, version_module.UNKNOWN_BUILD)
                with mock.patch("common.services.BUILD_NUMBER", reloaded.BUILD_NUMBER):
                    row = record_activity(
                        actor=None, action=ActivityLog.Action.LOGIN, entity_type="Probe"
                    )
                self.assertEqual(row.app_build, version_module.UNKNOWN_BUILD)
            finally:
                importlib.reload(version_module)

    def test_a_valid_build_is_an_int(self):
        self.assertEqual(version_module._coerce_build(" 42 "), 42)

    def test_an_unreadable_file_yields_no_values_rather_than_an_error(self):
        original = version_module._VERSION_FILE
        try:
            version_module._VERSION_FILE = original.parent / "does-not-exist-VERSION"
            self.assertEqual(version_module._read_version_file(), {})
        finally:
            version_module._VERSION_FILE = original

    def test_version_string_is_the_one_display_form(self):
        self.assertEqual(
            version_module.VERSION_STRING,
            f"{version_module.APP_VERSION} (build {version_module.BUILD_NUMBER})",
        )


class HealthEndpointTests(TestCase):
    def test_health_publishes_the_build_the_frontend_compares_against(self):
        with broker_reachable():
            resp = self.client.get(reverse("health"))
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["app_version"], version_module.APP_VERSION)
        self.assertEqual(body["build"], version_module.BUILD_NUMBER)

    def test_health_does_not_use_the_key_version(self):
        """`version` is the optimistic-lock counter everywhere else; reusing it here would make
        two unrelated things share a name across the whole API."""
        self.assertNotIn("version", self.client.get(reverse("health")).json())


class AuditBuildStampTests(TestCase):
    def test_every_audit_row_records_the_build_that_wrote_it(self):
        actor = get_user_model().objects.create_user(username="stamp", password="x")
        row = record_activity(actor=actor, action=ActivityLog.Action.LOGIN, entity_type="User")
        self.assertEqual(row.app_build, version_module.BUILD_NUMBER)

    def test_the_column_is_nullable_so_pre_stamp_rows_stay_valid(self):
        """Absence means "written before build stamping", not "unknown" — the append-only trail
        is never back-filled."""
        row = ActivityLog.objects.create(action="login", entity_type="User", app_build=None)
        row.refresh_from_db()
        self.assertIsNone(row.app_build)
