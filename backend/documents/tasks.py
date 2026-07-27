"""Celery entry points for letter generation (§6.6).

Thin wrappers: the work lives in `generation`, so it can be called directly from a test without
a broker. Failures re-raise after the job row has recorded the reason, so the worker log and the
UI tell the same story.
"""

from celery import shared_task

from .generation import run_eligibility_job, run_process_list_job


@shared_task(name="documents.generate_eligibility")
def generate_eligibility(job_id: int) -> None:
    run_eligibility_job(job_id)


@shared_task(name="documents.generate_process_list")
def generate_process_list(job_id: int) -> None:
    run_process_list_job(job_id)
