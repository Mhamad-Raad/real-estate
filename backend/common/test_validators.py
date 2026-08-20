"""Field validation, and the fact that BOTH doors that create a client enforce it (§4.1).

Written from real defects: the API accepted and **stored** a phone of `"hello world"`, a birth
date in 2099 and another in 1300. Each of those reached the database, and a birth year prints on
a government letter.
"""

from datetime import date, timedelta

from django.test import TestCase
from rest_framework import serializers
from rest_framework.test import APITestCase

from accounts.models import User
from catalog.models import Category
from clients.serializers import ClientSerializer
from common.validators import (
    BIRTH_FUTURE,
    BIRTH_TOO_OLD,
    PHONE_CHARS,
    PHONE_LENGTH,
    PID_FORMAT,
    STEP_END_BEFORE_START,
    validate_birth_date,
    validate_phone,
    validate_pid,
)


class PhoneValidatorTests(TestCase):
    def test_accepts_the_shapes_the_office_actually_types(self):
        for value in ("07701234567", "0770 123 4567", "+964 770 123 4567", "(0770) 1234567"):
            self.assertEqual(validate_phone(value), value)

    def test_rejects_a_dash(self):
        """User decision 2026-08-11 — and the API must agree with the box, which refuses it as it
        is typed; otherwise one field has two different rules."""
        with self.assertRaises(serializers.ValidationError) as caught:
            validate_phone("0770-123-4567")
        self.assertEqual(str(caught.exception.detail[0]), PHONE_CHARS)

    def test_accepts_arabic_indic_digits(self):
        """The office writes numbers in these — the letters, the ID cards and the screens all do.
        An ASCII-only gate told a lawyer who typed digits that the field needs digits."""
        for value in ("٠٧٧٠١٢٣٤٥٦٧", "٠٧٧٠ ١٢٣ ٤٥٦٧", "۰۷۷۰۱۲۳۴۵۶۷"):
            self.assertEqual(validate_phone(value), value)

    def test_arabic_indic_digits_are_still_counted_for_length(self):
        """Accepting the script must not accidentally exempt it from the length rule."""
        with self.assertRaises(serializers.ValidationError) as caught:
            validate_phone("٠٧٧٠")
        self.assertEqual(str(caught.exception.detail[0]), PHONE_LENGTH)

    def test_blank_is_still_allowed(self):
        """The field is optional; not every beneficiary leaves a number."""
        self.assertEqual(validate_phone(""), "")

    def test_rejects_letters(self):
        """The reported defect: words were accepted into a dialable field."""
        for value in ("hello world", "0770 call me", "٠٧٧٠abc"):
            with self.assertRaises(serializers.ValidationError) as caught:
                validate_phone(value)
            # The message is an i18n key, so the office reads it in their own language (§9).
            self.assertEqual(str(caught.exception.detail[0]), PHONE_CHARS)

    def test_rejects_a_number_of_the_wrong_length(self):
        with self.assertRaises(serializers.ValidationError) as caught:
            validate_phone("0770")
        self.assertEqual(str(caught.exception.detail[0]), PHONE_LENGTH)
        with self.assertRaises(serializers.ValidationError):
            validate_phone("077012345678901")

    def test_a_country_code_does_not_count_toward_the_national_length(self):
        """Counting the `964` made the international form 13 digits and refused it — caught by
        this test before it shipped, because the docstring claimed a stripping the code lacked."""
        self.assertEqual(validate_phone("+9647701234567"), "+9647701234567")
        # …but the code is only ignored when it leaves a valid national number behind.
        with self.assertRaises(serializers.ValidationError):
            validate_phone("+96477012345678901")


class BirthDateValidatorTests(TestCase):
    def test_accepts_a_plausible_date(self):
        value = date(1980, 5, 4)
        self.assertEqual(validate_birth_date(value), value)

    def test_none_passes_through(self):
        """A spouse birth date is null for an unmarried client."""
        self.assertIsNone(validate_birth_date(None))

    def test_rejects_the_future(self):
        with self.assertRaises(serializers.ValidationError) as caught:
            validate_birth_date(date.today() + timedelta(days=1))
        self.assertEqual(str(caught.exception.detail[0]), BIRTH_FUTURE)

    def test_rejects_a_mistyped_century(self):
        """`1300` for `1980` parses and stores; only a lower bound catches it."""
        with self.assertRaises(serializers.ValidationError) as caught:
            validate_birth_date(date(1300, 1, 1))
        self.assertEqual(str(caught.exception.detail[0]), BIRTH_TOO_OLD)


class ClientSerializerValidationTests(TestCase):
    """The rules must reach the serializer, and name the field that broke them."""

    def _errors(self, **overrides):
        payload = {
            "full_name": "A",
            "pid": "199900000001",
            "mother_full_name": "M",
            "marital_status": "single",
            "date_of_birth": "1990-01-01",
            **overrides,
        }
        serializer = ClientSerializer(data=payload)
        serializer.is_valid()
        return serializer.errors

    def test_a_bad_phone_is_reported_against_the_phone_field(self):
        """Per-field, so the screen can mark that one input red rather than the whole form."""
        self.assertIn("phone", self._errors(phone="hello world"))

    def test_a_future_birth_date_is_reported_against_its_own_field(self):
        errors = self._errors(date_of_birth=(date.today() + timedelta(days=1)).isoformat())
        self.assertIn("date_of_birth", errors)

    def test_a_valid_record_still_passes(self):
        self.assertEqual(self._errors(phone="07701234567"), {})

    def test_a_new_pid_must_be_twelve_digits(self):
        """Office rule, 2026-08-20 — this REVERSES the 2026-08-10 "leave the pid alone" decision,
        but only for a PID being written. See the pair below for what still passes."""
        self.assertEqual(self._errors(pid="DEMO-0001"), {"pid": [PID_FORMAT]})
        self.assertEqual(self._errors(pid="19900101123"), {"pid": [PID_FORMAT]})   # 11
        self.assertEqual(self._errors(pid="1990010112345"), {"pid": [PID_FORMAT]})  # 13
        self.assertEqual(self._errors(pid="19900101 234"), {"pid": [PID_FORMAT]})

    def test_twelve_digits_passes_including_leading_and_trailing_zeros(self):
        """`pid` is a string precisely so `007…` and `…000` survive a round trip — the office
        asked for that explicitly."""
        self.assertEqual(self._errors(pid="199001011234"), {})
        self.assertEqual(self._errors(pid="000000000000"), {})
        self.assertEqual(self._errors(pid="007123456000"), {})

    def test_an_arabic_indic_pid_is_accepted_and_stored_as_ascii(self):
        """The office types numbers in their own script (§9), so refusing `١٩٩…` would refuse a
        correctly-entered ID — but `١٩٩٠` and `1990` are different strings to the dedup index, so
        accepting both without folding them would open a duplicate straight through the guard."""
        self.assertEqual(validate_pid("١٩٩٠٠١٠١١٢٣٤"), "199001011234")
        self.assertEqual(validate_pid("۱۹۹۰۰۱۰۱۱۲۳۴"), "199001011234")


class BothCreationDoorsValidateTests(APITestCase):
    """Intake and scan-confirm both create a client — the It.8 rule: same act, same guard.

    The scan path is the one the office actually uses, and it carries its OWN hand-written copy of
    the client fields, so a rule added only to `ClientSerializer` would miss it entirely.
    """

    def setUp(self):
        self.lawyer = User.objects.create_user("vlw", password="pw12345678")
        self.category = Category.objects.create(code="V", name="V")
        self.client.force_authenticate(self.lawyer)

    def _intake(self, **client_overrides):
        return self.client.post(
            "/api/v1/processes/",
            {
                "category": self.category.id,
                "assigned_lawyer": self.lawyer.id,
                "client_data": {
                    "full_name": "A",
                    "pid": "199900000009",
                    "mother_full_name": "M",
                    "marital_status": "single",
                    "date_of_birth": "1990-01-01",
                    **client_overrides,
                },
            },
            format="json",
        )

    def test_intake_refuses_a_phone_of_words(self):
        resp = self._intake(phone="hello world")

        self.assertEqual(resp.status_code, 400)
        # Nested under the nested serializer — the shape the frontend has to be able to read.
        self.assertIn("phone", resp.data["client_data"])

    def test_intake_refuses_a_future_birth_date(self):
        resp = self._intake(date_of_birth=(date.today() + timedelta(days=365)).isoformat())

        self.assertEqual(resp.status_code, 400)
        self.assertIn("date_of_birth", resp.data["client_data"])

    def test_the_scan_confirm_door_refuses_the_same_phone(self):
        from ocr.views import ConfirmSerializer

        serializer = ConfirmSerializer(data={"full_name": "A", "phone": "hello world"})

        self.assertFalse(serializer.is_valid())
        self.assertIn("phone", serializer.errors)

    def test_the_scan_confirm_door_refuses_the_same_birth_date(self):
        from ocr.views import ConfirmSerializer

        serializer = ConfirmSerializer(
            data={"full_name": "A", "date_of_birth": (date.today() + timedelta(days=1)).isoformat()}
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("date_of_birth", serializer.errors)


class StepDateTests(APITestCase):
    """A step cannot finish before it started — the pair prints on the compiled cover sheet."""

    def setUp(self):
        from clients.models import Client
        from processes.models import Process

        self.lawyer = User.objects.create_user("sdlw", password="pw12345678")
        category = Category.objects.create(code="S", name="S")
        client = Client.objects.create(
            full_name="A", pid="199900000021", mother_full_name="M", date_of_birth=date(1990, 1, 1)
        )
        # Through the service, which is what creates the five steps (§14.2) — `Process.objects
        # .create()` alone leaves a case with none.
        from processes.services import create_process

        self.process = create_process(
            client=client, category=category, assigned_lawyer=self.lawyer, actor=self.lawyer
        )
        self.step = self.process.steps.order_by("step_number").first()
        self.client.force_authenticate(self.lawyer)

    def _patch(self, **body):
        return self.client.patch(
            f"/api/v1/processes/{self.process.id}/steps/{self.step.step_number}/",
            {"version": self.step.version, **body},
            format="json",
        )

    def test_an_end_before_the_start_is_refused_against_the_end_field(self):
        resp = self._patch(start_date="2026-05-10", end_date="2026-05-01")

        self.assertEqual(resp.status_code, 400)
        # DRF keeps a dict-of-string ValidationError as a bare string, not a one-item list.
        self.assertIn(STEP_END_BEFORE_START, str(resp.data["end_date"]))

    def test_the_same_day_is_fine(self):
        """A step opened and closed on one day is ordinary, not an error."""
        resp = self._patch(start_date="2026-05-10", end_date="2026-05-10")

        self.assertEqual(resp.status_code, 200, resp.data)

    def test_an_unparseable_date_is_a_400_not_a_500(self):
        """`save_step` assigns straight onto the model, so this reached `save()` and blew up."""
        resp = self._patch(start_date="not-a-date")

        self.assertEqual(resp.status_code, 400)
        self.assertIn("start_date", resp.data)
