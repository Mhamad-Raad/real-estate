"""Scheduled maintenance tasks (§13.2).

Thin wrappers, like `documents/tasks.py`: the work lives in a service so it can be called from a
management command and tested without a broker, and the task is only how Beat reaches it.
"""

from celery import shared_task

from .backup import run_backup


@shared_task(name="common.run_backup")
def nightly_backup() -> str:
    """Take the nightly `pg_dump` + manifest and prune old ones. Returns the file written."""
    return str(run_backup())
