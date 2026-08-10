"""The controlled document-type vocabulary — every type is labelled and nameable (§6.7).

`processes.test_missing_codes` already checks that every *required* type has an English label, but
it walks the missing-requirement codes, and an **optional** type is never missing by definition. So
a type like `Request` could ship with no label at all and no test would notice — the same gap that
let `case_summary` reach production label-less in It.4. These guards cover the whole list instead.
"""

from django.test import SimpleTestCase

from common import translations

from .document_types import DOCUMENT_TYPE_NAMES_CKB, DOCUMENT_TYPES, name_ckb


class DocumentTypeVocabularyTests(SimpleTestCase):
    def test_every_type_has_an_english_label(self):
        english = translations.load("en")
        unlabelled = [
            f"{dt.code} -> {dt.display_key}"
            for dt in DOCUMENT_TYPES
            if not translations.has_label(english, dt.display_key)
        ]
        self.assertEqual(unlabelled, [], f"missing en.json labels: {unlabelled}")

    def test_every_type_has_a_sorani_name_for_its_filename(self):
        # `name_ckb` falls back to the raw code so a file is never named blank — which means a
        # forgotten entry surfaces as `Request.pdf` in the office's folders, not as an error.
        missing = [dt.code for dt in DOCUMENT_TYPES if dt.code not in DOCUMENT_TYPE_NAMES_CKB]
        self.assertEqual(missing, [], f"no Sorani filename name: {missing}")

    def test_the_request_is_an_optional_step_1_upload(self):
        # Pins the office's three decisions: it belongs to Step 1, it never blocks the step, and it
        # is scanned back in rather than produced by the system (2026-08-10).
        request = next(dt for dt in DOCUMENT_TYPES if dt.code == "Request")
        self.assertEqual(request.step, 1)
        self.assertFalse(request.required)
        self.assertFalse(request.generated)
        self.assertEqual(name_ckb("Request"), "داواکاری")
