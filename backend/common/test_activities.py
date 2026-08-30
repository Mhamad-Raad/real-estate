"""The Activities page: RBAC, filtering, and the append-only guarantee (§11.2, §11.3)."""

from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import User

from .models import ActivityLog
from .services import record_activity
from .testing import insert_backdated_activity


class ActivitiesTestBase(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="adm", password="pw12345678", role=User.Role.ADMIN
        )
        self.lawyer = User.objects.create_user(username="lw", password="pw12345678")
        self.created = record_activity(
            actor=self.lawyer,
            action=ActivityLog.Action.CREATE,
            entity_type="Process",
            entity_id=7,
            after={"status": "draft"},
        )
        self.deleted = record_activity(
            actor=self.admin,
            action=ActivityLog.Action.DELETE,
            entity_type="Client",
            entity_id=3,
            before={"full_name": "Someone"},
        )


class ActivitiesRbacTests(ActivitiesTestBase):
    def test_requires_authentication(self):
        self.assertEqual(self.client.get(reverse("activity-list")).status_code, 401)

    def test_lawyer_is_refused(self):
        """The trail exposes every actor's before/after data, so it is admin-only."""
        self.client.force_authenticate(self.lawyer)
        self.assertEqual(self.client.get(reverse("activity-list")).status_code, 403)
        self.assertEqual(self.client.get(reverse("activity-vocabulary")).status_code, 403)

    def test_admin_may_read(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get(reverse("activity-list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)


class ActivitiesAppendOnlyTests(ActivitiesTestBase):
    """The API must expose no way to alter history — not even for an admin (§11.2)."""

    def setUp(self):
        super().setUp()
        self.client.force_authenticate(self.admin)

    def test_create_is_not_allowed(self):
        response = self.client.post(
            reverse("activity-list"), {"action": "create", "entity_type": "Process"}
        )
        self.assertEqual(response.status_code, 405)

    def test_update_and_delete_are_not_allowed(self):
        detail = reverse("activity-detail", args=[self.created.id])
        self.assertEqual(self.client.patch(detail, {"action": "login"}).status_code, 405)
        self.assertEqual(self.client.delete(detail).status_code, 405)
        self.created.refresh_from_db()
        self.assertEqual(self.created.action, ActivityLog.Action.CREATE)


class ActivitiesFilterTests(ActivitiesTestBase):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(self.admin)

    def _ids(self, **params):
        response = self.client.get(reverse("activity-list"), params)
        return [row["id"] for row in response.data["results"]]

    def test_filters_by_actor_action_and_entity(self):
        self.assertEqual(self._ids(actor=self.lawyer.id), [self.created.id])
        self.assertEqual(self._ids(action="delete"), [self.deleted.id])
        self.assertEqual(self._ids(entity_type="Process"), [self.created.id])
        self.assertEqual(self._ids(entity_type="Process", entity_id="7"), [self.created.id])

    def test_filters_by_date_range(self):
        # Inserted old rather than back-dated with `update()` — the table is append-only in the
        # database now (common/0003), which the old form of this test tripped over.
        old_id = insert_backdated_activity(
            timezone.now() - timedelta(days=10),
            action=ActivityLog.Action.LOGIN,
            entity_type="User",
            entity_id=1,
        )
        today = timezone.localtime().date().isoformat()
        self.assertIn(old_id, self._ids())
        self.assertNotIn(old_id, self._ids(created_after=today))

    def test_malformed_filters_are_400_not_500(self):
        """Query strings are raw user input; reaching `filter()` unvalidated raises a 500."""
        for params in (
            {"actor": "notanumber"},
            {"created_after": "garbage"},
            {"action": "nonsense"},
            {"created_after": "2026-05-02", "created_before": "2026-05-01"},
        ):
            response = self.client.get(reverse("activity-list"), params)
            self.assertEqual(response.status_code, 400, params)

    def test_valid_but_unmatched_filters_return_an_empty_page(self):
        """A well-formed filter that matches nothing is a 200, not an error."""
        response = self.client.get(reverse("activity-list"), {"actor": 999999})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)

    def test_newest_first(self):
        self.assertEqual(self._ids(), [self.deleted.id, self.created.id])

    def test_row_exposes_actor_name_and_before_after(self):
        row = self.client.get(reverse("activity-list")).data["results"][1]
        self.assertEqual(row["actor_username"], "lw")
        self.assertEqual(row["after"], {"status": "draft"})

    def test_vocabulary_lists_actions_and_only_present_entity_types(self):
        data = self.client.get(reverse("activity-vocabulary")).data
        self.assertIn({"value": "create", "label": "Create"}, data["actions"])
        # Derived from the data — it must not advertise a type nothing ever wrote.
        self.assertEqual(sorted(data["entity_types"]), ["Client", "Process"])
        self.assertEqual([a["username"] for a in data["actors"]], ["adm", "lw"])

    def test_vocabulary_keeps_a_deactivated_actor(self):
        """An audit page that cannot filter by a departed user fails when it matters most."""
        self.lawyer.is_active = False
        self.lawyer.save(update_fields=["is_active"])

        data = self.client.get(reverse("activity-vocabulary")).data
        self.assertIn("lw", [a["username"] for a in data["actors"]])

    def test_deleted_actor_does_not_break_the_row(self):
        """`actor` is PROTECT + nullable; a null actor (anonymous login) must still render."""
        record_activity(actor=None, action=ActivityLog.Action.LOGIN, entity_type="User")
        response = self.client.get(reverse("activity-list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"][0]["actor_username"], "")
