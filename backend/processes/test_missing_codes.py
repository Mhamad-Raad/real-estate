"""Every `missing` code the API can emit must have a label in the UI (§3.6).

The codes cross the API boundary as machine strings, so a new requirement added in `status.py`
would otherwise reach a lawyer as a raw i18n key. This derives the vocabulary from real output —
no second list to keep in step — and checks it against the shipped English translations. The
existing i18n parity test then guarantees ar/ckb carry the same keys.
"""

from django.test import TestCase

from accounts.models import User
from common import translations

from .models import ProcessStep
from .services import create_process
from .status import missing_requirements
from clients.factories import make_client


class MissingCodeVocabularyTests(TestCase):
    def setUp(self):
        self.lawyer = User.objects.create_user("vlw", password="pw12345678")
        # Married, so the marital-conditional spouse-ID requirement is part of the vocabulary too.
        self.client_row = make_client(
            full_name="Vocab",
            pid="V-1",
            mother_full_name="Vocab Mother",
            marital_status="married",
        )
        # No category, no land, no docs, no entries, a fired duplicate flag and the out-of-city
        # flag on Step 3 — the state that makes every step report everything it can want.
        self.process = create_process(
            client=self.client_row, assigned_lawyer=self.lawyer, actor=self.lawyer
        )
        self.process.duplicate_flagged = True
        self.process.save(update_fields=["duplicate_flagged"])
        step3 = self.process.steps.get(step_number=3)
        step3.out_of_city_flag = True
        step3.save(update_fields=["out_of_city_flag"])

    def _all_codes(self) -> set[str]:
        codes = set()
        for step in self.process.steps.all().order_by("step_number"):
            codes.update(missing_requirements(self.process, step.step_number, step))
        return codes

    def test_the_probe_case_exercises_every_code_shape(self):
        codes = self._all_codes()
        shapes = {c.split(":")[0] if ":" in c else "field" for c in codes}
        self.assertEqual(shapes, {"field", "doc", "institute", "step"})
        # Sanity-check the bare field codes, the ones with no backing enum to fall back on.
        for expected in ("land_id", "category", "duplicate_flag", "start_date", "custom_entries"):
            self.assertIn(expected, codes)

    def test_every_code_has_an_english_label(self):
        english = translations.load("en")

        from catalog.institutes import INSTITUTES

        institute_keys = {code: key for code, key, _step in INSTITUTES}

        untranslated = []
        for code in sorted(self._all_codes()):
            kind, _, value = code.partition(":")
            if kind == "institute":
                key = institute_keys.get(value)
            elif kind == "doc":
                key = f"workflow.docType.{value}"
            elif kind == "step":
                key = f"workflow.step{value}"
            else:
                key = f"workflow.missing.{code}"
            if not key or not translations.has_label(english, key):
                untranslated.append(f"{code} -> {key}")

        self.assertEqual(untranslated, [], f"missing en.json labels: {untranslated}")

    def test_a_completed_step_reports_nothing_missing(self):
        # The invariant the whole design rests on: complete ⇔ empty missing list.
        step5 = self.process.steps.get(step_number=5)
        self.process.steps.filter(step_number__lt=5).update(status=ProcessStep.Status.COMPLETE)
        self.assertEqual(missing_requirements(self.process, 5, step5), [])
