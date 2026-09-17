from django.test import SimpleTestCase

from ocr.bench import CardResult, FieldScore, normalise_name, score_field, similarity, summarise


class NormaliseNameTests(SimpleTestCase):
    def test_folds_letter_forms_a_reader_would_call_the_same_name(self):
        self.assertEqual(normalise_name("هونەر"), normalise_name("هونه ر".replace(" ", "")))
        self.assertEqual(normalise_name("علی"), normalise_name("علي"))
        self.assertEqual(normalise_name("  أحمد   كريم "), "احمد كريم")

    def test_keeps_letters_that_make_a_different_name(self):
        self.assertNotEqual(normalise_name("ڕەئوف"), normalise_name("رەئوف"))


class SimilarityTests(SimpleTestCase):
    def test_bounds(self):
        self.assertEqual(similarity("abc", "abc"), 1.0)
        self.assertEqual(similarity("", "abc"), 0.0)
        self.assertAlmostEqual(similarity("kitten", "sitting"), 1 - 3 / 7)


class ScoreFieldTests(SimpleTestCase):
    def test_three_outcomes(self):
        self.assertEqual(score_field("pid", "199822238795", {"value": "199822238795"}).outcome, "correct")
        self.assertEqual(score_field("pid", "199822238795", {"value": ""}).outcome, "empty")
        self.assertEqual(score_field("pid", "199822238795", {"value": "199822238796"}).outcome, "wrong")

    def test_no_truth_is_not_scored(self):
        self.assertEqual(score_field("date_of_birth", "", {"value": "2000-01-01"}).outcome, "n/a")

    def test_a_confident_misread_is_flagged(self):
        score = score_field("date_of_birth", "1900-07-01", {"value": "2000-07-01", "verified": True})
        self.assertEqual(score.outcome, "wrong")
        self.assertTrue(score.verified_but_wrong)

    def test_names_ignore_how_a_compound_is_spaced(self):
        self.assertEqual(
            score_field("full_name", "احمد عادل عبدالزهرة", {"value": "احمد عادل عبد الزهرة"}).outcome,
            "correct",
        )


class SummariseTests(SimpleTestCase):
    def test_counts_skip_unscored_cards(self):
        results = [
            CardResult("A", "scan", 1.0, {"pid": FieldScore("correct", 1.0), "date_of_birth": FieldScore("n/a")}),
            CardResult("B", "scan", 2.0, {"pid": FieldScore("wrong", 0.5), "date_of_birth": FieldScore("empty")}),
        ]
        summary = summarise(results)
        self.assertEqual(summary["pid"]["cards"], 2)
        self.assertEqual(summary["pid"]["correct"], 1)
        self.assertEqual(summary["pid"]["mean_similarity"], 0.75)
        self.assertEqual(summary["date_of_birth"]["cards"], 1)
        self.assertEqual(summary["date_of_birth"]["empty"], 1)
