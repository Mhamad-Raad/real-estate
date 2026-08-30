"""The Step-3 out-of-city rows: their order on screen, and their name (UC-110, UC-111)."""

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from catalog.models import Category
from clients.factories import make_client
from documents.factories import make_pdf

from .models import Process
from .services import create_process


class OutOfCityRowTests(APITestCase):
    def setUp(self):
        self.lawyer = User.objects.create_user("ooc_lw", password="pw12345678")
        self.category = Category.objects.create(code="A", name="A")
        self.process = create_process(
            client=make_client(full_name="Karwan", pid="197712120099", category=self.category),
            assigned_lawyer=self.lawyer,
            actor=self.lawyer,
            category=self.category,
        )
        self.client.force_authenticate(self.lawyer)

    def _add(self, name=None):
        payload = {"process": self.process.id, "step_number": 3, "is_custom": True}
        if name is not None:
            payload["custom_name"] = name
        resp = self.client.post(reverse("institute-entry-list"), payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        return resp.data

    def _entry_names(self):
        resp = self.client.get(reverse("process-detail", args=[self.process.id]))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        return [e["custom_name"] for e in resp.data["institute_entries"] if e["is_custom"]]

    def test_the_rows_are_asked_for_in_filing_order(self):
        """UC-110, and the assertion that actually bites.

        The office saw two out-of-city rows swap places when one of them was saved: with no
        `ordering` the DB is free to return them however the heap holds them, and an UPDATE moves
        the row it touched. That heap order **cannot be reproduced in a fresh test database** — a
        two-row update stays HOT, so the index entry never moves and the rows come back in the
        order they went in either way. What can be pinned is the query: it must ask for an order
        rather than take what it is given.
        """
        sql = str(self.process.institute_entries.all().query)

        self.assertRegex(sql, r'ORDER BY .*"process_institute_entry"\."id" ASC')

    def test_saving_one_row_does_not_move_it_past_the_other(self):
        """The same rule as the office sees it — read the test above for why this one would pass
        on its own."""
        first = self._add("First")
        self._add("Second")

        resp = self.client.patch(
            reverse("institute-entry-detail", args=[first["id"]]),
            {"process": self.process.id, "version": first["version"], "custom_name": "First edited"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)

        self.assertEqual(self._entry_names(), ["First edited", "Second"])

    def test_a_row_is_added_without_a_name(self):
        """UC-111: refusing a blank one is what forced the row to be born under a placeholder
        name, which then shipped whenever nobody overwrote it."""
        self.assertEqual(self._add()["custom_name"], "")

    def test_a_step_with_an_unnamed_row_is_not_complete(self):
        """The requirement did not go away — it moved to where it does not fire mid-edit."""
        step = self.process.steps.get(step_number=3)
        step.out_of_city_flag = True
        step.save(update_fields=["out_of_city_flag"])
        self._add()

        resp = self.client.get(reverse("process-detail", args=[self.process.id]))
        third = next(s for s in resp.data["steps"] if s["step_number"] == 3)

        self.assertIn("custom_entries", third["missing"])

    def test_a_named_and_finished_row_settles_that_requirement(self):
        """The requirement did not move to nowhere: filling the row in still clears it."""
        step = self.process.steps.get(step_number=3)
        step.out_of_city_flag = True
        step.save(update_fields=["out_of_city_flag"])
        entry = self._add()
        resp = self.client.patch(
            reverse("institute-entry-detail", args=[entry["id"]]),
            {
                "process": self.process.id,
                "version": entry["version"],
                "custom_name": "بەڕێوەبەرایەتی دەرەوەی شار",
                "assigned_lawyer": self.lawyer.id,
                "approval_status": "approved",
                "approval_date": "2026-08-01",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.client.post(
            reverse("document-list"),
            {
                "process": self.process.id,
                "step_number": 3,
                "document_type": "InstituteDoc",
                "institute_entry": entry["id"],
                "file": SimpleUploadedFile("ooc.pdf", make_pdf(), content_type="application/pdf"),
            },
            format="multipart",
        )

        resp = self.client.get(reverse("process-detail", args=[self.process.id]))
        third = next(s for s in resp.data["steps"] if s["step_number"] == 3)

        self.assertNotIn("custom_entries", third["missing"])

    def test_a_custom_row_still_belongs_to_step_3_only(self):
        """The rule that did not move: out-of-city rows exist in one step."""
        resp = self.client.post(
            reverse("institute-entry-list"),
            {"process": self.process.id, "step_number": 2, "is_custom": True},
            format="json",
        )

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Process.objects.get(pk=self.process.id).institute_entries.exists())
