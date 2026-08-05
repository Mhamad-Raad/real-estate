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
        """The system owns the sequence end to end (§3.8).

        UC-062 briefly made this editable so the office could choose where the sequence resumed;
        they reversed that in UC-064 — the number is issued automatically per category and by
        nothing else. `unique_code` is absent from `ProcessUpdateSerializer`, so a caller that
        sends one is ignored rather than obeyed.
        """
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
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        process.refresh_from_db()
        self.assertEqual(process.unique_code, "A1")

    def test_a_code_cannot_be_chosen_at_intake_either(self):
        """The other half of the same rule — the intake payload has no say in the number."""
        resp = self.client.post(
            reverse("process-list"),
            {
                "client_data": client_data(pid="199505050103"),
                "category": self.category.id,
                "unique_code": "A999",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Process.objects.get(pk=resp.data["id"]).unique_code, "A1")


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


class CategoryIsRequiredAtIntakeTests(APITestCase):
    """Every new case must be numberable, so it must name a category (UC-056, the office's rule)."""

    def setUp(self):
        self.lawyer = User.objects.create_user("req_lw", password="pw12345678")
        self.category = Category.objects.create(code="A", name="A")
        self.client.force_authenticate(self.lawyer)

    def test_a_case_cannot_be_opened_without_a_category(self):
        resp = self.client.post(
            reverse("process-list"), {"client_data": client_data(pid="199505050201")}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("category", resp.data)
        self.assertFalse(Process.all_objects.filter(client__pid="199505050201").exists())

    def test_a_null_category_is_refused_too(self):
        resp = self.client.post(
            reverse("process-list"),
            {"client_data": client_data(pid="199505050202"), "category": None},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_naming_a_category_opens_the_case_and_numbers_it(self):
        resp = self.client.post(
            reverse("process-list"),
            {"client_data": client_data(pid="199505050203"), "category": self.category.id},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Process.objects.get(pk=resp.data["id"]).unique_code)


class UnifiedSearchTests(APITestCase):
    """One box finds a case by name, national ID **or** the office's code (§4.3)."""

    def setUp(self):
        self.lawyer = User.objects.create_user("srch_lw", password="pw12345678")
        self.category = Category.objects.create(code="A", name="A")
        self.target = create_process(
            client=make_client(
                full_name="Karwan Ahmed", pid="197712120099", category=self.category
            ),
            assigned_lawyer=self.lawyer, actor=self.lawyer, category=self.category,
        )
        create_process(
            client=make_client(full_name="Someone Else", pid="196505050088", category=self.category),
            assigned_lawyer=self.lawyer, actor=self.lawyer, category=self.category,
        )
        self.client.force_authenticate(self.lawyer)

    def _codes(self, term):
        resp = self.client.get(reverse("process-list"), {"search": term})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        return [row["unique_code"] for row in resp.data["results"]]

    def test_finds_a_case_by_its_code(self):
        self.assertIn(self.target.unique_code, self._codes(self.target.unique_code))

    def test_finds_a_case_by_a_fragment_of_its_code(self):
        """The office quotes `A1` when it means the run, not only the whole code."""
        self.assertIn(self.target.unique_code, self._codes(self.target.unique_code[:2]))

    def test_still_finds_a_case_by_a_name_fragment(self):
        self.assertIn(self.target.unique_code, self._codes("Karwan"))

    def test_still_finds_a_case_by_a_national_id_fragment(self):
        self.assertIn(self.target.unique_code, self._codes("771212"))

    def test_a_term_matching_nothing_returns_nothing(self):
        self.assertEqual(self._codes("zzzz-no-such-thing"), [])

    def test_the_row_carries_the_code_so_the_list_can_show_it(self):
        resp = self.client.get(reverse("process-list"))
        self.assertIn("unique_code", resp.data["results"][0])
