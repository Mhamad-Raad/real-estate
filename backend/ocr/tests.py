"""MRZ parsing and draft building (§6.5).

Pure logic — no Tesseract, no database, no files — so these run fast and stay meaningful even on
a machine without the OCR toolchain installed. The MRZ fixtures are the real shape read off a
KRG national ID during the accuracy spike, with the identifying digits changed.
"""

from datetime import date

from django.test import TestCase

from . import extraction, mrz

# The three TD1 lines as Tesseract returns them, with a valid document number and dates.
MRZ_LINES = [
    "IDIRQG761033550200103487811<<<",
    "0108124M3506156IRQ<<<<<<<<<<<5",
    "ZHAWXAY<<MXHMD<<<<<<<<<<<<<<<<",
]
BACK_TEXT = "\n".join(MRZ_LINES)

FRONT_TEXT = """البطاقة الوطنية/ كارتى نيشتماتى
200103487811
الإسح ]ناو : محمد
لآب /باوك :+ رعد
الج ١ بير : رضا
انلقب ۲ نازناو : زهاوی
الام / دايك : دلسوز
الجد ١ بيز : على
ج الجنس رەگ : ذكر
"""


class CheckDigitTests(TestCase):
    def test_known_icao_examples(self):
        self.assertEqual(mrz.check_digit("520727"), "3")
        self.assertEqual(mrz.check_digit("AB2134"), "5")

    def test_filler_counts_as_zero(self):
        self.assertEqual(mrz.char_value("<"), 0)
        self.assertEqual(mrz.char_value("A"), 10)

    def test_a_filler_check_digit_verifies_nothing(self):
        """`<` is not a check digit; treating it as one would fake a verification."""
        self.assertFalse(mrz.verify("010812", "<"))


class DateParsingTests(TestCase):
    def test_two_digit_year_resolves_to_the_past_for_a_birth_date(self):
        self.assertEqual(mrz.parse_yymmdd("010812"), date(2001, 8, 12))
        self.assertEqual(mrz.parse_yymmdd("850101"), date(1985, 1, 1))

    def test_a_birth_year_just_under_the_pivot_does_not_land_in_the_future(self):
        """`28` is below the pivot, so the pivot alone would read it as 2028 — a birth date
        cannot be in the future, and that direction is the more reliable rule."""
        parsed = mrz.parse_yymmdd("280315")
        self.assertEqual(parsed, date(1928, 3, 15))
        self.assertLess(parsed, date.today())

    def test_an_impossible_date_is_rejected_not_guessed(self):
        # OCR readily produces month 00 or day 32; inventing a date would be worse than none.
        self.assertIsNone(mrz.parse_yymmdd("010013"))
        self.assertIsNone(mrz.parse_yymmdd("013299"))
        self.assertIsNone(mrz.parse_yymmdd("abcdef"))


class MrzParsingTests(TestCase):
    def test_finds_the_zone_among_other_page_text(self):
        page = "جهة الاصدار\n2025/06/16\n" + BACK_TEXT
        self.assertEqual(mrz.find_mrz_lines(page), MRZ_LINES)

    def test_ignores_ordinary_lines(self):
        self.assertEqual(mrz.find_mrz_lines("just a normal line of text"), [])

    def test_parses_the_checked_fields(self):
        result = mrz.parse(BACK_TEXT)
        self.assertEqual(result.date_of_birth, date(2001, 8, 12))
        self.assertEqual(result.sex, "M")
        self.assertEqual(result.nationality, "IRQ")
        self.assertIn("date_of_birth", result.verified)
        self.assertTrue(result.is_usable)

    def test_the_expiry_date_is_skipped_but_its_offsets_still_hold(self):
        """The office identifies the holder; whether the card is in date is not its business.
        Nationality sits after the expiry field, so the offsets must still be right."""
        result = mrz.parse(BACK_TEXT)
        self.assertFalse(hasattr(result, "expiry_date"))
        self.assertEqual(result.nationality, "IRQ")

    def test_parses_the_name_line(self):
        result = mrz.parse(BACK_TEXT)
        self.assertEqual(result.surname, "ZHAWXAY")
        self.assertEqual(result.given_names, "MXHMD")

    def test_a_corrupted_date_fails_its_check_digit(self):
        """The point of the MRZ: a misread is detectable, not silently accepted."""
        broken = ["0908124M3506156IRQ<<<<<<<<<<<5"]
        result = mrz.parse_td1([MRZ_LINES[0]] + broken)
        self.assertNotIn("date_of_birth", result.verified)

    def test_garbage_input_yields_an_unusable_result_rather_than_raising(self):
        result = mrz.parse("no machine readable zone here")
        self.assertFalse(result.is_usable)
        self.assertIsNone(result.date_of_birth)

    def test_a_dense_line_above_the_zone_does_not_shift_every_field(self):
        """The zone is the bottom of the card; anything else MRZ-shaped is above it. Reading the
        first three candidates instead of the last three lost the whole back of the card."""
        page = "SERIAL<<<NO<<<12345<<<ABCDEFGHIJKLM\n" + BACK_TEXT
        result = mrz.parse(page)
        self.assertEqual(result.date_of_birth, date(2001, 8, 12))
        self.assertEqual(result.national_id, "200103487811")
        self.assertTrue(result.is_usable)


class FrontParsingTests(TestCase):
    def test_maps_the_labelled_lines_by_position(self):
        parts = extraction.parse_front_fields(FRONT_TEXT)
        self.assertEqual(parts["given_name"], "محمد")
        self.assertEqual(parts["father_name"], "رعد")
        self.assertEqual(parts["father_grandfather"], "رضا")
        self.assertEqual(parts["surname"], "زهاوی")
        self.assertEqual(parts["mother_name"], "دلسوز")
        self.assertEqual(parts["mother_grandfather"], "على")

    def test_the_second_grandfather_completes_the_mothers_name(self):
        """The dedup key (§3.7) is the mother's own name PLUS her father's."""
        parts = extraction.parse_front_fields(FRONT_TEXT)
        self.assertEqual(extraction.compose_mother_full_name(parts), "دلسوز على")

    def test_full_name_uses_the_fathers_line_not_the_mothers(self):
        parts = extraction.parse_front_fields(FRONT_TEXT)
        self.assertEqual(extraction.compose_full_name(parts), "محمد رعد رضا زهاوی")


class DraftTests(TestCase):
    def test_pid_agreeing_across_front_and_mrz_is_marked_verified(self):
        draft = extraction.build_draft(front_text=FRONT_TEXT, back_text=BACK_TEXT, pid_confidence=96)
        self.assertEqual(draft.pid.value, "200103487811")
        self.assertEqual(draft.pid.source, "mrz+front")
        self.assertTrue(draft.pid.verified)

    def test_pid_disagreement_warns_instead_of_silently_picking_one(self):
        """The PID is the 'no land twice' key — a wrong one blocks or admits the wrong person."""
        front = FRONT_TEXT.replace("200103487811", "200103487899")
        draft = extraction.build_draft(front_text=front, back_text=BACK_TEXT)
        self.assertFalse(draft.pid.verified)
        self.assertTrue(any("does not match" in w for w in draft.warnings))

    def test_birth_date_comes_from_the_mrz_and_is_check_digit_verified(self):
        draft = extraction.build_draft(front_text=FRONT_TEXT, back_text=BACK_TEXT)
        self.assertEqual(draft.date_of_birth.value, "2001-08-12")
        self.assertTrue(draft.date_of_birth.verified)

    def test_an_unreadable_back_warns_rather_than_producing_confident_dates(self):
        draft = extraction.build_draft(front_text=FRONT_TEXT, back_text="unreadable")
        self.assertTrue(draft.date_of_birth.is_empty)
        self.assertTrue(any("machine-readable zone" in w for w in draft.warnings))

    def test_a_field_that_could_not_be_read_says_so(self):
        """Partial failure is the normal photocopy case: one copier pass breaks the birth date's
        check digit while the document number still verifies, so the MRZ warning stays silent.
        Without this the lawyer got an empty required field and no reason for it."""
        broken_dob = ["IDIRQG761033550200103487811<<<", "9999994M3506156IRQ<<<<<<<<<<<5"]
        draft = extraction.build_draft(front_text=FRONT_TEXT, back_text="\n".join(broken_dob))

        self.assertTrue(draft.date_of_birth.is_empty)
        self.assertTrue(any("date of birth" in w for w in draft.warnings))
        # The rest of the card read fine, so it must not claim those failed too.
        self.assertFalse(any("card number" in w for w in draft.warnings))

    def test_several_unread_fields_are_named_in_one_warning(self):
        draft = extraction.build_draft(front_text="", back_text="")
        unread = [w for w in draft.warnings if "Could not read" in w and "by hand" in w]
        self.assertEqual(len(unread), 1, "one combined warning, not one per field")
        for label in ("the card number", "the full name", "the date of birth"):
            self.assertIn(label, unread[0])

    def test_a_fully_read_card_carries_no_unread_warning(self):
        draft = extraction.build_draft(front_text=FRONT_TEXT, back_text=BACK_TEXT)
        self.assertFalse(any("please enter" in w for w in draft.warnings))

    def test_a_missing_mother_grandfather_is_flagged(self):
        front = FRONT_TEXT.replace("الجد ١ بيز : على\n", "")
        draft = extraction.build_draft(front_text=front, back_text=BACK_TEXT)
        self.assertTrue(any("mother's father" in w for w in draft.warnings))

    def test_the_family_number_is_not_mistaken_for_the_card_number(self):
        """The front carries a second 12-digit number. Page order alone picks the wrong one, so
        the MRZ decides which candidate is the card number."""
        front = "ژمارەی خێزان 987654321012\n" + FRONT_TEXT
        draft = extraction.build_draft(front_text=front, back_text=BACK_TEXT)
        self.assertEqual(draft.pid.value, "200103487811")
        self.assertTrue(draft.pid.verified)

    def test_without_an_mrz_the_first_number_is_still_offered(self):
        """No cross-check available — propose something and let the human check it."""
        self.assertEqual(extraction.find_pid("987654321012 and 200103487811"), "987654321012")

    def test_draft_serialises_for_the_verify_screen(self):
        payload = extraction.build_draft(
            front_text=FRONT_TEXT, back_text=BACK_TEXT, pid_confidence=96
        ).as_dict()
        self.assertEqual(payload["fields"]["pid"]["value"], "200103487811")
        self.assertIn("confidence", payload["fields"]["full_name"])


class ImageUploadTests(TestCase):
    """A photographed ID must reach the store as a PDF (§6.7)."""

    def test_a_jpeg_is_converted_on_upload(self):
        from io import BytesIO

        from PIL import Image

        from documents import filestore

        buffer = BytesIO()
        Image.new("RGB", (60, 40), (255, 0, 0)).save(buffer, format="JPEG")
        jpeg = buffer.getvalue()

        self.assertTrue(filestore.looks_like_image(jpeg))
        self.assertFalse(filestore.looks_like_pdf(jpeg))

        converted = filestore.image_to_pdf(jpeg)
        self.assertTrue(filestore.is_readable_pdf(converted))

    def test_transparency_is_flattened_onto_white(self):
        """A PNG with alpha would otherwise render on a black background."""
        from io import BytesIO

        from PIL import Image

        from documents import filestore

        buffer = BytesIO()
        Image.new("RGBA", (40, 40), (0, 0, 0, 0)).save(buffer, format="PNG")
        self.assertTrue(filestore.is_readable_pdf(filestore.image_to_pdf(buffer.getvalue())))
