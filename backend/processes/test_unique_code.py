"""The office's case number — allocation, immutability, and the never-reissued rule (§3.8, UC-056)."""

from django.db import IntegrityError, transaction
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase, APITransactionTestCase

from accounts.models import User
from catalog.models import Category
from clients.factories import client_data, make_client

from .models import Process
from .services import allocate_unique_code, create_process


class UniqueCodeAllocationTests(APITestCase):
    def setUp(self):
        self.lawyer = User.objects.create_user("code_lw", password="pw12345678")
        self.a = Category.objects.create(code="A", name="A")
        self.g = Category.objects.create(code="G", name="General")

    def _case(self, category, pid):
        return create_process(
            client=make_client(pid=pid, category=category),
            assigned_lawyer=self.lawyer,
            actor=self.lawyer,
            category=category,
        )

    def test_the_first_case_in_a_category_is_number_one(self):
        self.assertEqual(self._case(self.a, "199001010001").unique_code, "A1")

    def test_each_category_counts_on_its_own(self):
        """`A1…` and `G1…` are separate runs — the letter is the category, not a shared prefix."""
        self.assertEqual(self._case(self.a, "199001010002").unique_code, "A1")
        self.assertEqual(self._case(self.g, "199001010003").unique_code, "G1")
        self.assertEqual(self._case(self.a, "199001010004").unique_code, "A2")
        self.assertEqual(self._case(self.g, "199001010005").unique_code, "G2")

    def test_a_soft_deleted_case_keeps_its_number_for_ever(self):
        """The invariant: retired, never reissued. Gaps in the sequence are correct."""
        first = self._case(self.a, "199001010006")
        self.assertEqual(first.unique_code, "A1")
        first.is_deleted = True
        first.save(update_fields=["is_deleted"])

        # The office moves a case between categories by deleting and re-opening (UC-059), so this
        # is the common path — reusing A1 would put two different cases on the same printed number.
        self.assertEqual(self._case(self.a, "199001010007").unique_code, "A2")

    def test_a_case_without_a_category_gets_no_code(self):
        """It cannot complete Step 1 either — `category` is in that step's `missing` list."""
        process = create_process(
            client=make_client(pid="199001010008"),
            assigned_lawyer=self.lawyer,
            actor=self.lawyer,
        )
        self.assertEqual(process.unique_code, "")

    def test_blank_codes_do_not_collide_with_each_other(self):
        """The constraint excludes the blank, or a second category-less case would be rejected."""
        for pid in ("199001010009", "199001010010"):
            create_process(
                client=make_client(pid=pid), assigned_lawyer=self.lawyer, actor=self.lawyer
            )
        self.assertEqual(Process.objects.filter(unique_code="").count(), 2)

    def test_a_category_whose_code_prefixes_another_is_counted_separately(self):
        """`A` and `AB` must not read each other's numbers — `AB1` is not `A`'s number 'B1'."""
        ab = Category.objects.create(code="AB", name="AB")
        self._case(self.a, "199001010011")           # A1
        self.assertEqual(self._case(ab, "199001010012").unique_code, "AB1")
        self.assertEqual(self._case(self.a, "199001010013").unique_code, "A2")

    def test_the_database_refuses_a_duplicate_code(self):
        """The storage-level backstop, in case anything ever slips past the lock."""
        first = self._case(self.a, "199001010014")
        clash = self._case(self.g, "199001010015")
        clash.unique_code = first.unique_code
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                clash.save(update_fields=["unique_code"])


class UniqueCodeApiTests(APITestCase):
    def setUp(self):
        self.lawyer = User.objects.create_user("code_api", password="pw12345678")
        self.category = Category.objects.create(code="A", name="A")
        self.client.force_authenticate(self.lawyer)

    def test_intake_allocates_a_code_and_returns_it(self):
        resp = self.client.post(
            reverse("process-list"),
            {"client_data": client_data(pid="199505050101"), "category": self.category.id},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        detail = self.client.get(reverse("process-detail", args=[resp.data["id"]]))
        self.assertEqual(detail.data["unique_code"], "A1")

    def test_the_code_cannot_be_edited(self):
        process = create_process(
            client=make_client(pid="199505050102", category=self.category),
            assigned_lawyer=self.lawyer,
            actor=self.lawyer,
            category=self.category,
        )
        resp = self.client.patch(
            reverse("process-detail", args=[process.id]),
            {"unique_code": "A999", "version": process.version},
            format="json",
        )
        # Not in the update serializer at all, so it is ignored rather than applied.
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        process.refresh_from_db()
        self.assertEqual(process.unique_code, "A1")


class UniqueCodeConcurrencyTests(APITransactionTestCase):
    """The reason allocation takes a row lock: two computers open a case at the same moment."""

    def test_two_concurrent_allocations_do_not_collide(self):
        import threading

        from django.db import connections

        lawyer = User.objects.create_user("race_lw", password="pw12345678")
        category = Category.objects.create(code="A", name="A")
        codes, errors = [], []

        def open_case(pid):
            try:
                with transaction.atomic():
                    codes.append(
                        create_process(
                            client=make_client(pid=pid, category=category),
                            assigned_lawyer=lawyer,
                            actor=lawyer,
                            category=category,
                        ).unique_code
                    )
            except Exception as exc:  # surfaced below rather than swallowed in the thread
                errors.append(exc)
            finally:
                connections.close_all()

        threads = [
            threading.Thread(target=open_case, args=(pid,))
            for pid in ("199001020001", "199001020002")
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [], f"allocation raised under concurrency: {errors}")
        self.assertEqual(sorted(codes), ["A1", "A2"], "two cases were given the same code")
