"""The production account bootstrap (§7, It.8 finding).

`seed_dev` was the only way to get a first user and it ships `admin`/`admin12345` as a superuser.
An install that went live on it would have had a published password on an account that bypasses
the app's own role checks. These tests hold the properties that make this command a safe
replacement — above all that it refuses to be a silent no-op.
"""

from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from accounts.models import User


class CreateAdminTests(TestCase):
    def _run(self, **kwargs):
        out = StringIO()
        call_command("create_admin", stdout=out, **kwargs)
        return out.getvalue()

    def test_it_creates_an_administrator(self):
        self._run(username="office_admin", password="a-long-real-passphrase")

        user = User.objects.get(username="office_admin")
        self.assertEqual(user.role, User.Role.ADMIN)
        self.assertTrue(user.check_password("a-long-real-passphrase"))

    def test_it_is_NOT_a_django_superuser(self):
        """`django.contrib.admin` was removed as a second, unaudited write path (It.8). A
        superuser here would be a step back toward one."""
        self._run(username="office_admin", password="a-long-real-passphrase")

        user = User.objects.get(username="office_admin")
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_staff)

    def test_it_refuses_the_exact_pair_seed_dev_shipped(self):
        """`admin` / `admin12345`. **Django accepts this pair** — its similarity validator scores
        it 0.667 against a 0.7 threshold — so the command carries its own rule. Measured, and the
        reason this test exists at all."""
        with self.assertRaises(CommandError):
            self._run(username="admin", password="admin12345")

        self.assertFalse(User.all_objects.filter(username="admin").exists())

    def test_it_refuses_the_published_dev_password_for_ANY_username(self):
        """`admin12345` is in this repo, its docs and every runbook example. Django accepts it for
        any username that does not contain it, so it is blocked by name."""
        with self.assertRaises(CommandError):
            self._run(username="office_admin", password="admin12345")

        self.assertFalse(User.all_objects.filter(username="office_admin").exists())

    def test_it_refuses_a_common_password(self):
        with self.assertRaises(CommandError):
            self._run(username="office_admin", password="password123")

        self.assertFalse(User.all_objects.filter(username="office_admin").exists())

    def test_it_refuses_a_short_password(self):
        with self.assertRaises(CommandError):
            self._run(username="office_admin", password="abc")

    def test_it_refuses_to_overwrite_an_existing_user(self):
        """Not idempotent on purpose — a command that 'succeeds' while doing nothing is how a
        default-password account survives an install."""
        User.objects.create_user("office_admin", password="a-long-real-passphrase")

        with self.assertRaises(CommandError):
            self._run(username="office_admin", password="another-long-passphrase")

    def test_it_also_refuses_when_the_existing_user_is_soft_deleted(self):
        """`all_objects`, not the default manager: a deleted row still owns the username, and the
        unique index would reject the insert with a 500 instead of this message."""
        user = User.objects.create_user("office_admin", password="a-long-real-passphrase")
        user.is_deleted = True
        user.save(update_fields=["is_deleted"])

        with self.assertRaises(CommandError):
            self._run(username="office_admin", password="another-long-passphrase")
