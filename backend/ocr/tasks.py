"""Celery entry point for card reading (§6.5).

Thin wrapper: the work lives in `services`, so it can be called directly from a test without a
broker. A failure re-raises after the scan row has recorded the reason, so the worker log and the
review screen tell the same story.
"""

from celery import shared_task

from .services import read_scan


@shared_task(name="ocr.read_card_scan")
def read_card_scan(scan_id: int) -> None:
    read_scan(scan_id)


@shared_task(name="ocr.requeue_stuck_scans")
def requeue_stuck_scans_task() -> list[int]:
    """Beat entry point for the recovery sweep (§6.3) — nothing scheduled it until It.9."""
    from .sweep import requeue_stuck_scans

    return requeue_stuck_scans()


@shared_task(name="ocr.discard_abandoned_scans")
def discard_abandoned_scans_task() -> list[int]:
    """Beat entry point for the abandoned-scan sweep: an unfiled ID card must not sit in the
    store indefinitely (§6.3, §11 — the row survives as the record)."""
    from .sweep import discard_abandoned_scans

    return discard_abandoned_scans()
