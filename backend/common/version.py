"""The running build's identity — declared once in the repo-root `VERSION` file.

Resolution is **environment first, file second**. The backend image is built from `backend/`
alone, so it can never contain a repo-root file; the image bakes the values in as `APP_VERSION`
and `APP_BUILD` instead. Neither source is required: an unresolvable build degrades to
`0.0.0 (build 0)` rather than stopping the app from coming up, because a version stamp must
never be the reason an offline office computer fails to start.

Note the naming: `version` is already the optimistic-lock counter on every model and serializer
(§7.2), so the app's own version is `app_version` / `build` everywhere it is exposed.
"""

from __future__ import annotations

import os
from pathlib import Path

# backend/common/version.py → backend/common → backend → repo root
_VERSION_FILE = Path(__file__).resolve().parents[2] / "VERSION"

UNKNOWN_VERSION = "0.0.0"
UNKNOWN_BUILD = 0


def _read_version_file() -> dict[str, str]:
    """Parse the `KEY=value` VERSION file, ignoring comments. Absent inside a built image."""
    try:
        text = _VERSION_FILE.read_text(encoding="utf-8")
    except OSError:
        return {}
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def _coerce_build(raw: str | None) -> int:
    """A malformed build number degrades to the 'unknown' marker instead of raising at import."""
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return UNKNOWN_BUILD


_FILE_VALUES = _read_version_file()

APP_VERSION: str = os.getenv("APP_VERSION") or _FILE_VALUES.get("APP_VERSION") or UNKNOWN_VERSION
BUILD_NUMBER: int = _coerce_build(os.getenv("APP_BUILD") or _FILE_VALUES.get("APP_BUILD"))

# One display form, so a support call, the About screen and the audit trail all read alike.
VERSION_STRING: str = f"{APP_VERSION} (build {BUILD_NUMBER})"
