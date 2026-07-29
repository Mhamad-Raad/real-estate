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
