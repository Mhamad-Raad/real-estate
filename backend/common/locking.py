"""Optimistic concurrency helper — stale writes get HTTP 409 (§4.1, §12)."""

from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError


class StaleVersion(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "This record was modified by someone else. Reload and try again."
    default_code = "stale_version"


def check_version(instance, expected_version, *, required: bool = False) -> None:
    """Enforce optimistic locking: 409 if the client's base `version` is stale.

    `required=True` (every update path) rejects a missing version with 400 so the lock
    can't be silently skipped; `required=False` lets creates opt out (no prior version).
    """
    if expected_version is None:
        if required:
            raise ValidationError({"version": "This field is required to edit an existing record."})
        return
    if int(expected_version) != instance.version:
        raise StaleVersion()
