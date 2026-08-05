"""The rescue pass must not cost more than it can possibly return (UC-065).

An imported PDF took **9–11 minutes** to read and the office gave up and typed the details by
hand. The cause was not the engine being slow in general: the second-chance pass runs `--psm 6`,
which costs ~10× the automatic segmentation, over an image it had first **doubled** — and on a
scan of a full page it spent all of that on finding nothing, because a page is not a card.
"""

from django.test import SimpleTestCase

from . import reader


class FrameContentScalingTests(SimpleTestCase):
    def _image(self, width, height):
        from PIL import Image

        return Image.new("RGB", (width, height), "white")

    def test_a_small_card_is_still_enlarged(self):
        """The case the rescue exists for: a card occupying a corner of a sheet."""
        framed = reader.frame_content(self._image(600, 380))
        self.assertGreater(max(framed.size), 600)
        self.assertLessEqual(max(framed.size), reader.FRAMED_TARGET_LONG_EDGE + 1)

    def test_a_full_page_is_not_enlarged(self):
        """Doubling a page is what turned a read into a ten-minute wait."""
        page = self._image(2550, 3300)
        self.assertEqual(reader.frame_content(page).size, page.size)

    def test_the_enlargement_is_bounded_even_for_a_tiny_crop(self):
        framed = reader.frame_content(self._image(120, 80))
        self.assertLessEqual(max(framed.size), 120 * reader.MAX_FRAME_SCALE)


class CardShapeGateTests(SimpleTestCase):
    def _sized(self, width, height):
        class Fake:
            size = (width, height)

        return Fake()

    def test_a_card_shaped_region_is_accepted(self):
        # 85.6 × 54 mm, either way up.
        self.assertTrue(reader.looks_like_a_card(self._sized(856, 540)))
        self.assertTrue(reader.looks_like_a_card(self._sized(540, 856)))

    def test_a_full_page_is_rejected(self):
        """The user's own file framed to 1139×2699 — aspect 0.42, nothing like a card."""
        self.assertFalse(reader.looks_like_a_card(self._sized(1139, 2699)))

    def test_a_long_strip_is_rejected(self):
        self.assertFalse(reader.looks_like_a_card(self._sized(4000, 300)))

    def test_anything_without_dimensions_is_allowed_through(self):
        """The gate may only ever *withhold* the rescue, so when it cannot tell it must not be
        the thing that suppresses a reading."""
        self.assertTrue(reader.looks_like_a_card("not an image"))
        self.assertTrue(reader.looks_like_a_card(self._sized(0, 0)))
