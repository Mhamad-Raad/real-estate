"""Reading the shipped frontend translations from the backend, for the label guards (§9).

Several backend vocabularies cross the API as machine codes that the UI renders through an i18n
key — the missing-requirement codes (§3.6), the document types and the institutes (§6.7). Each has
a test asserting the key really exists in `en.json`, and the frontend's own parity test then
carries ar/ckb. Those tests all need the same two things, so they live here rather than being
re-derived per app: the *value* check is the subtle part, and a copy that got it wrong would
weaken the guard while still looking like one.
"""

import json
from pathlib import Path

from django.conf import settings


def locales_dir() -> Path | None:
    """Where the frontend translations are: the compose mount, else the sibling checkout."""
    return settings.FRONTEND_LOCALES_DIR


def load(locale: str = "en") -> dict:
    """The shipped translations for one language. Raises if the directory was never found."""
    directory = locales_dir()
    if directory is None:
        raise FileNotFoundError(
            "frontend locales not found — compose mounts them at /frontend_locales, "
            "and a native run expects frontend/src/i18n/locales beside backend/"
        )
    return json.loads((directory / f"{locale}.json").read_text(encoding="utf-8"))


def has_label(translations: dict, dotted_key: str) -> bool:
    """True only when the key resolves to a **non-empty string**.

    The `isinstance` check is the whole point: a key that lands on a translation *block* would
    otherwise count as translated, and the UI would render the raw key. `workflow.docType` is a
    dict and must fail; `workflow.docType.ClientID` is a string and must pass.
    """
    node = translations
    for part in dotted_key.split("."):
        if not isinstance(node, dict) or part not in node:
            return False
        node = node[part]
    return isinstance(node, str) and bool(node)
