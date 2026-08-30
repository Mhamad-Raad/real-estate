"""Every letter-template type the backend defines must have a UI label (§6.6, UC-008).

The class of bug this exists for: `case_summary` was added in It.4 and the frontend's own hardcoded
copy of the list never caught up, so the type was unreachable in the UI and its label rendered as
the raw key `templates.types.case_summary`. **The frontend i18n guard structurally cannot see
this** — it only checks the three locales agree with *each other*, and all three were equally
missing the key. Deriving the vocabulary from the enum is the only check that catches it.
"""

import unittest

from django.conf import settings
from django.test import TestCase

from common.translations import has_label, load

from .models import DocumentTemplate


@unittest.skipIf(
    settings.FRONTEND_LOCALES_DIR is None, "frontend locales not mounted (see docker-compose)"
)
class TemplateTypeVocabularyTests(TestCase):
    def test_every_template_type_has_an_english_label(self):
        translations = load("en")
        missing = [
            value
            for value in DocumentTemplate.TemplateType.values
            if not has_label(translations, f"templates.types.{value}")
        ]
        # ar/ckb are then guaranteed by the frontend's key-parity test.
        self.assertEqual(missing, [], f"No `templates.types.*` label for: {missing}")
