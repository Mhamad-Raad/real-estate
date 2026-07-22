"""Auth + audit invariant tests for the app shell (Iteration 0)."""

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from common.models import ActivityLog

from .models import User


class AuthFlowTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="lawyer1", password="pw12345678", role=User.Role.LAWYER
        )

    def test_login_returns_tokens_and_profile(self):
        resp = self.client.post(
            reverse("login"),
            {"username": "lawyer1", "password": "pw12345678"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("access", resp.data)
        self.assertIn("refresh", resp.data)
        self.assertEqual(resp.data["user"]["role"], "lawyer")

    def test_login_writes_audit_row(self):
        self.client.post(
            reverse("login"),
            {"username": "lawyer1", "password": "pw12345678"},
            format="json",
        )
        self.assertTrue(
            ActivityLog.objects.filter(action=ActivityLog.Action.LOGIN).exists()
        )

    def test_bad_credentials_rejected(self):
        resp = self.client.post(
            reverse("login"),
            {"username": "lawyer1", "password": "wrong"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_requires_authentication(self):
        resp = self.client.get(reverse("me"))
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_returns_current_user(self):
        self.client.force_authenticate(self.user)
        resp = self.client.get(reverse("me"))
        self.assertEqual(resp.data["username"], "lawyer1")

    def test_me_patch_updates_preferences_only(self):
        self.client.force_authenticate(self.user)
        resp = self.client.patch(
            reverse("me"), {"language": "en", "role": "admin"}, format="json"
        )
        self.user.refresh_from_db()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(self.user.language, "en")
        self.assertEqual(self.user.role, "lawyer")  # role is not self-editable

    def test_logout_blacklists_refresh_and_audits(self):
        login = self.client.post(
            reverse("login"),
            {"username": "lawyer1", "password": "pw12345678"},
            format="json",
        )
        refresh = login.data["refresh"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        resp = self.client.post(reverse("logout"), {"refresh": refresh}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_205_RESET_CONTENT)
        self.assertTrue(
            ActivityLog.objects.filter(action=ActivityLog.Action.LOGOUT).exists()
        )
        # A blacklisted refresh token can no longer mint access tokens.
        again = self.client.post(
            reverse("token_refresh"), {"refresh": refresh}, format="json"
        )
        self.assertEqual(again.status_code, status.HTTP_401_UNAUTHORIZED)
