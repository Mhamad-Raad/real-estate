"""Celery entry point for OCR (§6.5).

Thin wrapper: the work lives in `services`, so it can be called directly from a test without a
broker. A failure re-raises after the run row has recorded the reason, so the worker log and the
verify screen tell the same story.
"""

from celery import shared_task

from .services import execute_ocr


@shared_task(name="ocr.run")
def run_ocr(run_id: int) -> None:
    execute_ocr(run_id)
