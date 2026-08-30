"""Deleting a case releases its beneficiary, so the person can be entered again (UC-061).

`ix_client_pid_active` is partial on `is_deleted=False`, so a living client goes on holding their
national ID. Before this, deleting the only case left that person permanently unusable: intake
offers no "pick an existing client" (§5.7, UC-026), and re-entering them by hand hit the PID
conflict. These tests pin both halves — the release, and the restore that has to undo it.
"""

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from catalog.models import Category
from clients.factories import client_data, make_client
from clients.models import Client
from common.models import ActivityLog

from .models import Process
from .services import create_process


class DeleteReleasesTheClientTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user("rel_adm", password="pw12345678", role=User.Role.ADMIN)
        self.lawyer = User.objects.create_user("rel_lw", password="pw12345678")
        self.category = Category.objects.create(code="R", name="R")
        self.person = make_client(full_name="Released", pid="199001010001", category=self.category)
        self.process = create_process(
            client=self.person,
            assigned_lawyer=self.lawyer,
            actor=self.lawyer,
            category=self.category,
        )
        self.client.force_authenticate(self.admin)

    def _delete(self):
        return self.client.delete(reverse("process-detail", args=[self.process.id]))

    def test_deleting_the_case_soft_deletes_the_beneficiary(self):
        self.assertEqual(self._delete().status_code, status.HTTP_204_NO_CONTENT)

        self.assertFalse(Client.objects.filter(pk=self.person.pk).exists())
        # Soft, never hard — the row and its papers are still there for an admin to restore (§11.1).
        self.assertTrue(Client.all_objects.get(pk=self.person.pk).is_deleted)

    def test_the_national_id_is_free_afterwards_so_the_person_can_be_re_entered(self):
        """The whole point: opening a fresh case for the same human must now work."""
        self._delete()

        resp = self.client.post(
            reverse("process-list"),
            {"client_data": client_data(pid="199001010001"), "category": self.category.id},
            format="json",
        )

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Client.objects.filter(pid="199001010001").count(), 1)

    def test_the_release_is_audited_against_the_client(self):
        self._delete()
        entry = ActivityLog.objects.filter(
            entity_type="Client", entity_id=str(self.person.id), action=ActivityLog.Action.DELETE
        ).latest("created_at")
        self.assertEqual(entry.after["reason"], "case deleted")

    def test_a_person_with_another_live_case_keeps_their_record(self):
        """Their surviving case reads the person from here — its documents, its letter and its
        compiled file would all describe someone the register says is gone."""
        Process.objects.filter(pk=self.process.pk).update(
            overall_status=Process.OverallStatus.REJECTED
        )
        second = create_process(
            client=self.person,
            assigned_lawyer=self.lawyer,
            actor=self.lawyer,
            category=self.category,
        )

        self.assertEqual(self._delete().status_code, status.HTTP_204_NO_CONTENT)

        self.person.refresh_from_db()
        self.assertFalse(self.person.is_deleted)
        self.assertFalse(Process.objects.get(pk=second.pk).is_deleted)

    def test_a_lawyer_deleting_their_own_case_releases_the_client_too(self):
        """The cascade belongs to the delete, not to who performed it."""
        self.client.force_authenticate(self.lawyer)
        self.assertEqual(self._delete().status_code, status.HTTP_204_NO_CONTENT)
        self.assertTrue(Client.all_objects.get(pk=self.person.pk).is_deleted)


class RestoreBringsTheClientBackTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user("res_adm", password="pw12345678", role=User.Role.ADMIN)
        self.lawyer = User.objects.create_user("res_lw", password="pw12345678")
        self.category = Category.objects.create(code="S", name="S")
        self.person = make_client(full_name="Restored", pid="199001010002", category=self.category)
        self.process = create_process(
            client=self.person,
            assigned_lawyer=self.lawyer,
            actor=self.lawyer,
            category=self.category,
        )
        self.client.force_authenticate(self.admin)
        self.client.delete(reverse("process-detail", args=[self.process.id]))

    def _restore(self):
        return self.client.post(reverse("process-restore", args=[self.process.id]))

    def test_restoring_the_case_restores_the_beneficiary(self):
        self.assertEqual(self._restore().status_code, status.HTTP_200_OK)

        self.assertFalse(Client.all_objects.get(pk=self.person.pk).is_deleted)
        self.assertFalse(Process.all_objects.get(pk=self.process.pk).is_deleted)

    def test_a_restore_blocked_by_a_re_used_national_id_rolls_the_case_back_too(self):
        """Freeing the PID means someone else may now hold it — that is the feature working. The
        restore must then fail whole: a case handed back without its person is worse than none."""
        make_client(full_name="Re-entered", pid="199001010002", category=self.category)

        resp = self._restore()

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("pid", str(resp.data).lower())
        # Neither half survived — no half-restored case.
        self.assertTrue(Process.all_objects.get(pk=self.process.pk).is_deleted)
        self.assertTrue(Client.all_objects.get(pk=self.person.pk).is_deleted)

    def test_a_client_deleted_on_their_own_is_left_alone_by_an_unrelated_restore(self):
        """`restore_client_with_case` only ever touches the case's own beneficiary."""
        other = make_client(full_name="Unrelated", pid="199001010003", category=self.category)
        other.is_deleted = True
        other.save(update_fields=["is_deleted"])

        self._restore()

        self.assertTrue(Client.all_objects.get(pk=other.pk).is_deleted)
