"""Every validation message the API sends must have a translation (§9).

The validators answer with i18n **keys** rather than English sentences, so the office reads a
rejected field in Sorani. That trade only holds if the key resolves: an untranslated one reaches
the user as a raw `errors.phone.chars`, which is worse than the English it replaced.

Exactly the guard `document_types` and the institutes already carry, and for the same reason —
**the frontend's own i18n test cannot see this.** It only checks the three locales agree with each
other, and a key missing from all three is equally missing everywhere.
"""

import unittest

from django.conf import settings
from django.test import TestCase

from common.translations import has_label, load
from common.validators import VALIDATION_KEYS


@unittest.skipIf(
    settings.FRONTEND_LOCALES_DIR is None, "frontend locales not mounted (see docker-compose)"
)
class ValidationKeyTranslationTests(TestCase):
    def test_every_validation_key_has_an_english_label(self):
        translations = load("en")

        missing = [key for key in VALIDATION_KEYS if not has_label(translations, key)]

        # ar/ckb then follow from the frontend's key-parity test.
        self.assertEqual(missing, [], f"No translation for validation key(s): {missing}")

    def test_the_keys_live_under_the_namespace_the_frontend_matches_on(self):
        """`translateApiMessage` only translates `errors.*`; a key outside it would be printed raw."""
        stray = [key for key in VALIDATION_KEYS if not key.startswith("errors.")]

        self.assertEqual(stray, [], f"Validation key(s) outside the `errors.` namespace: {stray}")
