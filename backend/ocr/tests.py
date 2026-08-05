"""MRZ parsing and draft building (§6.5).

Pure logic — no Tesseract, no database, no files — so these run fast and stay meaningful even on
a machine without the OCR toolchain installed. The MRZ fixtures are the real shape read off a
KRG national ID during the accuracy spike, with the identifying digits changed.
"""

from datetime import date

from django.test import SimpleTestCase, TestCase

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


class SecondChanceReadTests(TestCase):
    """A card scanned onto a sheet defeats the automatic segmentation; a framed retry rescues it.

    Tesseract is stubbed so this stays pure logic — what is pinned is the *decision*: the retry
    only runs when the first pass found nothing, and it only wins when it found more. The same
    settings destroy a photographed card, so promoting them to the default is not an option.
    """

    def setUp(self):
        from pathlib import Path

        from . import reader

        self.Path = Path
        self.reader = reader
        self.calls = []
        self._real_read_side = reader.read_side
        self._real_load = reader.load_images
        self._real_frame = reader.frame_content

    def tearDown(self):
        self.reader.read_side = self._real_read_side
        self.reader.load_images = self._real_load
        self.reader.frame_content = self._real_frame

    def _patch(self, first: str, second: str):
        from .reader import SideRead

        def fake(image, *, psm=None):
            self.calls.append(psm)
            text = second if psm else first
            return SideRead(arabic_text=text, latin_text=text, digit_confidence=0)

        self.reader.read_side = fake
        self.reader.load_images = lambda path: ["front"]
        self.reader.frame_content = lambda image, **kw: image

    def test_a_scan_the_first_pass_cannot_read_is_retried_and_kept(self):
        self._patch(first="", second=FRONT_TEXT)
        draft = self.reader.read_card(self.Path("x.pdf"))
        self.assertIn(6, self.calls, "the framed retry never ran")
        self.assertTrue(any("read a second time" in w for w in draft.warnings))

    def test_a_card_the_first_pass_reads_is_never_retried(self):
        self._patch(first=FRONT_TEXT, second="")
        self.reader.read_card(self.Path("x.jpg"))
        self.assertNotIn(6, self.calls, "a readable card must not be re-read with the fallback")


class MrzDigitConfusionTests(SimpleTestCase):
    """Numeric MRZ fields survive the engine reading letters for digits (UC-068).

    The office's own card gave `9SO1016` for `9501016` — S for 5, O for 0. That cost the date of
    birth *and* its check digit, so the whole MRZ was reported unverified and the lawyer was told
    to enter dates by eye on a card whose MRZ was in fact perfectly readable.
    """

    LINES = [
        "IDIRQA3519035274199548017276<<<",
        "9SO1016M3S111080IRQ<<<<<<<K<<<5",
        "K<XTAWDYR<<<<<<<<<<<<<<<<<<<<<<",
    ]

    def test_the_birth_date_is_recovered_and_check_digit_verified(self):
        from .mrz import parse_td1

        result = parse_td1(self.LINES)

        self.assertEqual(str(result.date_of_birth), "1995-01-01")
        # Recovered *and* trusted: the check digit proves the correction was right, which is why
        # this is a safe repair rather than a guess.
        self.assertIn("date_of_birth", result.verified)

    def test_a_misread_letter_never_shortens_the_national_id(self):
        """The "no land twice" key must not be silently compacted (§3.7).

        Filtering the optional-data field to `isdigit()` **deleted** any letter the engine
        misread, so one bad character turned a 13-character read into 12 digits — the exact
        length of a real PID. The wrong number then looked entirely valid and was offered as the
        card number at confidence 70. Repair, or drop the field; never quietly shorten it.
        """
        from .mrz import parse_td1

        clean = parse_td1(
            ["IDIRQA3519035274199548017276<<<", self.LINES[1], self.LINES[2]]
        ).national_id
        smudged = parse_td1(
            ["IDIRQA351903527419954801727S<<<", self.LINES[1], self.LINES[2]]
        ).national_id

        self.assertEqual(len(clean), 13)
        # Repaired, not compacted — the length is what made a wrong value look right.
        self.assertEqual(len(smudged), len(clean))

    def test_a_field_that_cannot_be_repaired_is_dropped_whole(self):
        """Better nothing than a plausible wrong identifier: the front of the card then decides."""
        from .mrz import parse_td1

        result = parse_td1(
            ["IDIRQA35190352741995480172#6<<<", self.LINES[1], self.LINES[2]]
        )

        self.assertEqual(result.national_id, "")

    def test_the_document_number_keeps_its_letters(self):
        """The number legitimately contains letters — only its check digit is numeric."""
        from .mrz import parse_td1

        self.assertTrue(parse_td1(self.LINES).document_number.startswith("A"))


class IncompleteNameBlockTests(SimpleTestCase):
    """A name block too damaged to trust is left empty, never guessed at (§6.5, UC-068).

    The front is parsed **positionally** — first name-like line is the given name, second the
    father, and so on. On a poor scan only one line may survive, and position alone then declares
    it the applicant: on the office's card the only legible line was the MOTHER's, and it was
    offered as the beneficiary's name. An empty box asks the lawyer to type it; a wrong one
    invites them to accept it.
    """

    def test_a_single_surviving_line_proposes_no_name(self):
        from .extraction import compose_full_name, compose_mother_full_name

        parts = {"given_name": "زيرين"}  # in truth the mother's line, read into slot 0

        self.assertEqual(compose_full_name(parts), "")
        self.assertEqual(compose_mother_full_name(parts), "")

    def test_a_complete_block_is_still_composed(self):
        from .extraction import compose_full_name, compose_mother_full_name

        parts = {
            "given_name": "ئاودێر",
            "father_name": "محمدامین",
            "father_grandfather": "عبدالله",
            "mother_name": "زيرين",
            "mother_grandfather": "حسين",
        }

        self.assertEqual(compose_full_name(parts), "ئاودێر محمدامین عبدالله")
        self.assertEqual(compose_mother_full_name(parts), "زيرين حسين")
