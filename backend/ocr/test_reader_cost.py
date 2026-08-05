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


class SpeckleTests(SimpleTestCase):
    """Scanner dust must not stretch the frame down the whole sheet (UC-067).

    The office's own card scan is a card in the top-left corner of an otherwise blank page — the
    exact shape the rescue exists for. It read **nothing**, because the bounding box was computed
    from "more than 3 dark pixels in a row", and the faint speckle a flatbed leaves on blank paper
    cleared that on nearly every line. The box came out 1079×2643 — the page, not the card — so
    the reading was of mostly empty paper and, once UC-065 landed, was skipped as not card-shaped.
    """

    def _page_with_card_and_speckle(self):
        from PIL import Image, ImageDraw

        page = Image.new("RGB", (2550, 3300), "white")
        draw = ImageDraw.Draw(page)
        # The card: a filled block of roughly card proportions in the top-left corner.
        draw.rectangle([120, 140, 1100, 760], fill="grey")
        # Flatbed speckle: single dark specks scattered the length of the page.
        for y in range(900, 3250, 40):
            draw.point((300 + (y % 700), y), fill="black")
            draw.point((1500 - (y % 500), y), fill="black")
        return page

    def test_the_frame_finds_the_card_not_the_page(self):
        framed = reader.frame_content(self._page_with_card_and_speckle())

        # Card proportions (85.6 × 54 mm ≈ 1.59), not the 2.4-plus of a full sheet.
        aspect = max(framed.size) / min(framed.size)
        self.assertLess(aspect, 2.0, f"framed {framed.size} — the speckle stretched the box again")
        self.assertTrue(reader.looks_like_a_card(framed))

    def test_the_frame_still_keeps_a_card_that_fills_the_image(self):
        """A photographed card is already the whole frame; the rule must not eat into it."""
        from PIL import Image, ImageDraw

        card = Image.new("RGB", (1000, 630), "white")
        ImageDraw.Draw(card).rectangle([20, 20, 980, 610], fill="grey")

        framed = reader.frame_content(card)

        self.assertGreaterEqual(min(framed.size), 600)
        self.assertTrue(reader.looks_like_a_card(framed))
