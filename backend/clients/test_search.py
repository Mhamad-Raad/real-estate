"""One search box, matching a name fragment or a national-ID fragment (§4.3, UC-004/UC-005)."""

from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.models import User
from processes.services import create_process

from .factories import make_client
from .selectors import search_clients


class ClientSearchTests(APITestCase):
    def setUp(self):
        self.person = make_client(full_name="Married Smoke Person", pid="200103487811")
        self.other = make_client(full_name="کاروان ئەحمەد مستەفا", pid="199512120001")

    def test_a_name_fragment_matches(self):
        """The reported defect: `pers` found nothing while `person` did (similarity 0.182 < 0.3)."""
        self.assertIn(self.person, search_clients(search="pers"))

    def test_the_whole_word_still_matches(self):
        self.assertIn(self.person, search_clients(search="person"))

    def test_search_is_case_insensitive(self):
        self.assertIn(self.person, search_clients(search="SMOKE"))

    def test_a_first_name_matches_however_long_the_full_name_is(self):
        """Similarity dropped below threshold as a Kurdish name gained parts; ILIKE cannot."""
        self.assertIn(self.other, search_clients(search="کاروان"))

    def test_a_national_id_fragment_matches(self):
        self.assertIn(self.person, search_clients(search="0348"))

    def test_a_whole_national_id_matches(self):
        self.assertIn(self.person, search_clients(search="200103487811"))

    def test_search_does_not_match_an_unrelated_person(self):
        self.assertNotIn(self.other, search_clients(search="pers"))

    def test_the_exact_pid_filter_is_untouched(self):
        """API callers and the dedup path still get exact matching, not contains."""
        self.assertIn(self.person, search_clients(pid="200103487811"))
        self.assertNotIn(self.person, search_clients(pid="0348"))


class ProcessSearchTests(APITestCase):
    """The Processes list carried the identical defect — it must follow the same rule."""

    def setUp(self):
        self.lawyer = User.objects.create_user("search_lawyer", password="pw12345678")
        self.person = make_client(full_name="Married Smoke Person", pid="200103487811")
        self.process = create_process(
            client=self.person, assigned_lawyer=self.lawyer, actor=self.lawyer
        )
        self.client.force_authenticate(self.lawyer)

    def _ids(self, **params):
        resp = self.client.get(reverse("process-list"), params)
        return [row["id"] for row in resp.data["results"]]

    def test_a_name_fragment_matches(self):
        self.assertIn(self.process.id, self._ids(search="pers"))

    def test_a_national_id_fragment_matches(self):
        self.assertIn(self.process.id, self._ids(search="0348"))
