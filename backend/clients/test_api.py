"""API tests for the clients endpoints — dedup check + married-spouse validation (§4, §5.7)."""

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from catalog.models import Category
from common.validators import PID_TAKEN

from .models import Client
from .factories import client_data, make_client


class ClientApiTests(APITestCase):
    def setUp(self):
        self.lawyer = User.objects.create_user("lw", password="pw12345678")
        self.category = Category.objects.create(code="A", name="A")
        self.client.force_authenticate(self.lawyer)
        self.existing = make_client(
            full_name="Karwan", pid="111000000111", mother_full_name="Nasrin Hassan"
        )

    def test_duplicate_check_returns_pid_match(self):
        resp = self.client.post(
            reverse("client-duplicate-check"),
            {"pid": "111000000111", "mother_full_name": "x"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual([c["id"] for c in resp.data["pid_matches"]], [self.existing.id])

    def post_client(self, **overrides):
        """Create through the **intake** endpoint — `POST /clients/` is 405 since UC-026.

        The field rules live on `ClientSerializer`, which the intake payload nests, so this still
        exercises exactly the validation it always did; only the door changed.
        """
        payload = client_data(full_name="Alan", pid="222000000222", mother_full_name="Runak", **overrides)
        return self.client.post(
            reverse("process-list"),
            {"client_data": payload, "category": self.category.id},
            format="json",
        )

    def test_a_client_cannot_be_created_through_the_clients_api(self):
        """UC-026: a beneficiary is born in the Step-1 intake form, nowhere else (§7.2 — the
        boundary moves, it is not merely hidden)."""
        resp = self.client.post(
            reverse("client-list"),
            client_data(full_name="Nope", pid="999000000999", mother_full_name="Nope"),
            format="json",
        )

        self.assertEqual(resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_a_client_cannot_be_deleted_through_the_clients_api(self):
        target = make_client(full_name="Keep", pid="888000000888", mother_full_name="Keep")

        resp = self.client.delete(reverse("client-detail", args=[target.id]))

        self.assertEqual(resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_married_client_requires_every_spouse_field(self):
        """The letter prints a spouse row of name / birth date / mother — all three or none."""
        for field in ("spouse_name", "spouse_date_of_birth", "spouse_mother_full_name"):
            with self.subTest(missing=field):
                payload = client_data(
                    full_name="Alan",
                    pid="222000000222",
                    mother_full_name="Runak",
                    marital_status="married",
                )
                payload.pop(field)
                resp = self.client.post(
                    reverse("process-list"),
            {"client_data": payload, "category": self.category.id},
            format="json",
                )
                self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn(field, str(resp.data))

    def test_birth_date_is_required(self):
        payload = client_data(full_name="Alan", pid="222000000222", mother_full_name="Runak")
        payload.pop("date_of_birth")

        resp = self.client.post(
            reverse("process-list"),
            {"client_data": payload, "category": self.category.id},
            format="json",
        )

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("date_of_birth", str(resp.data))

    def test_unmarried_client_never_keeps_spouse_details(self):
        """A divorce must not leave the former spouse printed on the next generated letter."""
        married = make_client(
            full_name="Dashne",
            pid="333000000333",
            mother_full_name="Nian",
            marital_status="married",
            created_by=self.lawyer,  # a lawyer may only edit clients they entered (§4.2)
        )

        resp = self.client.patch(
            reverse("client-detail", args=[married.id]),
            {"marital_status": "divorced", "version": married.version},
            format="json",
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        married.refresh_from_db()
        self.assertEqual(married.spouse_name, "")
        self.assertEqual(married.spouse_mother_full_name, "")
        self.assertIsNone(married.spouse_date_of_birth)

    def test_create_client_ok(self):
        resp = self.post_client()

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_married_client_with_full_spouse_details_is_accepted(self):
        resp = self.post_client(marital_status="married")

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)



class PidTakenMessageTests(APITestCase):
    """A national ID already on file must say **whose** it is, in the office's language (§9).

    DRF generates a `UniqueValidator` for `pid` from the conditional index, and it answered
    `"client with this pid already exists."` — English, naming the column, and never the holder,
    which is the one thing the person typing needs. It is also the **only** uniqueness check on the
    edit path, so it could not simply be removed.
    """

    def setUp(self):
        self.admin = User.objects.create_user(
            "pid_admin", password="pw12345678", role=User.Role.ADMIN
        )
        self.client.force_authenticate(self.admin)
        self.category = Category.objects.create(code="P", name="P")
        self.existing = make_client(full_name="Karwan Ahmed", pid="197712120099")

    def _message(self, response):
        return response.data["pid"][0]

    def test_creating_a_case_on_a_taken_id_names_the_holder(self):
        resp = self.client.post(
            reverse("process-list"),
            {
                "client_data": {
                    "full_name": "Someone Else", "pid": "197712120099",
                    "mother_full_name": "M", "date_of_birth": "1980-01-01",
                },
            },
            format="json",
        )

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["client_data"]["pid"][0], f"{PID_TAKEN}:Karwan Ahmed")

    def test_editing_a_client_onto_a_taken_id_names_the_holder(self):
        """The edit path has no service check of its own — the serializer's validator is all there
        is — so this is the case that proves it was kept, not merely re-worded."""
        other = make_client(full_name="Someone Else", pid="196505050088")

        resp = self.client.patch(
            reverse("client-detail", args=[other.id]),
            {"pid": "197712120099", "version": other.version},
            format="json",
        )

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self._message(resp), f"{PID_TAKEN}:Karwan Ahmed")

    def test_a_client_may_still_be_saved_with_its_own_id(self):
        """The exclusion the parent validator does must survive: editing a phone number must not
        trip on the record's own PID."""
        resp = self.client.patch(
            reverse("client-detail", args=[self.existing.id]),
            {"phone": "07701234567", "version": self.existing.version},
            format="json",
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)

    def test_the_same_id_typed_in_arabic_indic_is_caught_before_the_database(self):
        """**The bug this validator was written to close.** DRF runs a field's validators *before*
        `validate_pid` folds Arabic-Indic digits, so the generated `UniqueValidator` compared the
        raw `١٩٧٧…` against a stored `1977…`, found nothing, and let the write reach
        `ix_client_pid_active` — an IntegrityError, i.e. **HTTP 500** in front of a lawyer typing
        digits the way this office writes them (§9). The edit path is where it bit, because it has
        no service check behind the serializer."""
        other = make_client(full_name="Someone Else", pid="196505050088")

        resp = self.client.patch(
            reverse("client-detail", args=[other.id]),
            {"pid": "١٩٧٧١٢١٢٠٠٩٩", "version": other.version},
            format="json",
        )

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self._message(resp), f"{PID_TAKEN}:Karwan Ahmed")

    def test_an_arabic_indic_id_nobody_holds_is_still_accepted(self):
        """The fold must not turn into a refusal: the office types every number this way."""
        other = make_client(full_name="Someone Else", pid="196505050088")

        resp = self.client.patch(
            reverse("client-detail", args=[other.id]),
            {"pid": "١٩٨٠٠١٠١٠٠٧٧", "version": other.version},
            format="json",
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        other.refresh_from_db()
        self.assertEqual(other.pid, "198001010077")  # stored canonical, never the raw script

    def test_a_soft_deleted_persons_id_is_free_again(self):
        """The validator's queryset hides soft-deleted rows, matching `ix_client_pid_active`. A
        deleted beneficiary must not lock their national ID for ever."""
        self.existing.is_deleted = True
        self.existing.save(update_fields=["is_deleted"])

        resp = self.client.post(
            reverse("process-list"),
            {
                "client_data": {
                    "full_name": "New Person", "pid": "197712120099",
                    "mother_full_name": "M", "date_of_birth": "1980-01-01",
                },
                "category": self.category.id,
            },
            format="json",
        )

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
