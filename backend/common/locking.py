"""Optimistic concurrency helper — stale writes get HTTP 409 (§4.1, §12)."""

from rest_framework import status
from rest_framework.exceptions import APIException


class StaleVersion(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "This record was modified by someone else. Reload and try again."
    default_code = "stale_version"


def check_version(instance, expected_version) -> None:
    """Raise 409 if the client's base `version` no longer matches the stored row."""
    if expected_version is None:
        return  # caller chose not to enforce (e.g. create)
    if int(expected_version) != instance.version:
        raise StaleVersion()
