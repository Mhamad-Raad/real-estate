"""Recovery and cleanup for staged card scans (§6.3, §6.7).

Two things go wrong on their own and neither shows up until someone looks:

* **A reading is lost.** The DB row — not the broker — is the source of truth for status, so if the
  host reboots mid-job the task in Redis is gone while the row still says `pending`. The scan
  would spin forever on the review screen. Re-enqueueing it is the whole reason status lives in
  the database (§6.3).
* **A scan is abandoned.** A lawyer photographs an ID, is interrupted, and never confirms. The
  staged file is a citizen's identity document sitting outside anyone's case folder, so it is
  deleted rather than kept indefinitely — but the row survives, because "a card was read and
  never became a record" is exactly the kind of fact the audit trail exists to keep (§11).
"""

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from common.models import ActivityLog
from common.services import record_activity

from .models import CardScan

# A read takes seconds; anything still running after this lost its task with the broker.
STUCK_AFTER = timedelta(minutes=30)
# Long enough to survive a weekend and an interrupted afternoon, short enough that an unfiled ID
# is not left lying in the store.
ABANDONED_AFTER = timedelta(days=14)


def requeue_stuck_scans(*, now=None, stuck_after: timedelta = STUCK_AFTER) -> list[int]:
    """Re-enqueue readings whose task vanished (host reboot, worker kill)."""
    from .tasks import read_card_scan

    now = now or timezone.now()
    stuck = CardScan.objects.filter(
        status__in=(CardScan.Status.PENDING, CardScan.Status.RUNNING),
        updated_at__lt=now - stuck_after,
        confirmed_at__isnull=True,
        discarded_at__isnull=True,
    ).exclude(file_path="")

    requeued = []
    for scan in stuck:
        # Back to pending: `running` on a scan nothing is working on is a lie the UI would show.
        scan.status = CardScan.Status.PENDING
        scan.save(update_fields=["status", "updated_at"])
        transaction.on_commit(lambda pk=scan.pk: read_card_scan.delay(pk))
        requeued.append(scan.pk)
    return requeued


def discard_abandoned_scans(
    *, actor=None, now=None, abandoned_after: timedelta = ABANDONED_AFTER
) -> list[int]:
    """Delete the staged image of any card never confirmed, keeping the row as the record."""
    now = now or timezone.now()
    abandoned = CardScan.objects.filter(
        created_at__lt=now - abandoned_after,
        confirmed_at__isnull=True,
        discarded_at__isnull=True,
    ).exclude(file_path="")

    discarded = []
    for scan in abandoned:
        with transaction.atomic():
            (settings.DOCUMENTS_ROOT / scan.file_path).unlink(missing_ok=True)
            scan.discarded_at = now
            scan.file_path = ""
            scan.save(update_fields=["discarded_at", "file_path", "updated_at"])
            record_activity(
                actor=actor,
                action=ActivityLog.Action.DELETE,
                entity_type="CardScan",
                entity_id=scan.pk,
                before={"document_type": scan.document_type, "uploaded_by": scan.uploaded_by_id},
                after={"reason": "abandoned — never confirmed"},
            )
        discarded.append(scan.pk)
    return discarded
