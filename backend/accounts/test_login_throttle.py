"""Sign-in is rate-limited, and only failures count (§12, It.8 finding).

Nothing throttled anything before this, so password guessing from the second office computer was
unbounded. The subtlety is which attempts consume the allowance: the two office computers are
shared by the whole office, so per-IP is per-**desk**. Counting successes would lock out a desk
because several lawyers signed in from it during a shift.

**These tests drive the SHIPPED rate rather than overriding it.** `override_settings` cannot change
it: DRF binds `SimpleRateThrottle.THROTTLE_RATES` as a class attribute at import, so the override
updates `api_settings` while the throttle keeps reading the dict it captured. A test that appeared
to set `3/min` was silently exercising the real `10/min` and proving nothing.
"""

from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from accounts.views import LoginThrottle

PASSWORD = "correct-horse-battery"


def allowance() -> int:
    """How many attempts the configured rate permits, read from the throttle itself."""
    throttle = LoginThrottle()
    throttle.scope = "login"
    return throttle.parse_rate(throttle.get_rate())[0]


class LoginThrottleTests(APITestCase):
    def setUp(self):
        User.objects.create_user("throttled", password=PASSWORD)
        self.limit = allowance()
        cache.clear()  # the throttle counts in the cache; a previous test must not bleed in

    def tearDown(self):
        cache.clear()

    def _attempt(self, password):
        return self.client.post(
            "/api/v1/auth/login/",
            {"username": "throttled", "password": password},
            format="json",
        )

    def test_a_rate_is_actually_configured(self):
        """A throttle class with no rate silently allows everything — the failure mode that looks
        exactly like a working guard."""
        self.assertGreater(self.limit, 0)

    def test_repeated_wrong_passwords_are_eventually_refused(self):
        for _ in range(self.limit):
            self.assertEqual(self._attempt("wrong").status_code, status.HTTP_401_UNAUTHORIZED)

        self.assertEqual(self._attempt("wrong").status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_a_correct_password_does_not_consume_the_allowance(self):
        """The shared-desk case: several lawyers signing in must not exhaust the limit."""
        for _ in range(self.limit * 2):
            self.assertEqual(self._attempt(PASSWORD).status_code, status.HTTP_200_OK)

    def test_a_locked_out_desk_cannot_get_in_even_with_the_right_password(self):
        """Once the limit is hit the door is shut, or a guesser would simply keep going."""
        for _ in range(self.limit + 1):
            self._attempt("wrong")

        self.assertEqual(self._attempt(PASSWORD).status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_nothing_else_is_throttled_by_default(self):
        """A lawyer filing papers all day must never be rate-limited out of their own work."""
        from django.conf import settings

        self.assertEqual(tuple(settings.REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"]), ())
