from django.test import SimpleTestCase
from PIL import Image, ImageDraw

from ocr import card_geometry


def sheet_with_card(*, angle: float = 0.0, extra_strip: bool = False) -> Image.Image:
    """A 300-dpi letter sheet with a blue card-sized rectangle on it, optionally tilted, and
    optionally touching a second blue strip — the merge the office's crumpled scans produced."""
    sheet = Image.new("RGB", (2550, 3300), "white")
    card = Image.new("RGBA", (1011, 638), (150, 200, 235, 255))
    ImageDraw.Draw(card).text((400, 200), "199259147844", fill="black")
    card = card.rotate(angle, expand=True, fillcolor=(0, 0, 0, 0))
    sheet.paste(card, (1300, 300), card)
    if extra_strip:
        ImageDraw.Draw(sheet).rectangle([1300, 300 + card.height, 2400, 300 + card.height + 25], fill=(150, 200, 235))
    return sheet


class FindCardTests(SimpleTestCase):
    def test_a_card_on_a_scanned_sheet_is_found_at_its_physical_size(self):
        centre, size, _ = card_geometry.find_card_on_sheet(sheet_with_card())
        self.assertAlmostEqual(max(size), 1011, delta=40)
        self.assertAlmostEqual(centre[0], 1300 + 1011 / 2, delta=30)

    def test_a_tilted_card_is_found_and_straightened_upright(self):
        card, found = card_geometry.card_image(sheet_with_card(angle=6))
        self.assertTrue(found)
        self.assertEqual(card.size, card_geometry.CARD_SIZE)

    def test_a_card_merged_with_a_neighbouring_strip_still_separates(self):
        rect = card_geometry.find_card_on_sheet(sheet_with_card(extra_strip=True))
        self.assertIsNotNone(rect)
        self.assertAlmostEqual(min(rect[1]), 638, delta=40)

    def test_a_photo_of_the_card_is_passed_through_untouched(self):
        photo = Image.new("RGB", (674, 442), (150, 200, 235))
        card, found = card_geometry.card_image(photo)
        self.assertFalse(found)
        self.assertIs(card, photo)

    def test_a_blank_sheet_has_no_card(self):
        self.assertIsNone(card_geometry.find_card_on_sheet(Image.new("RGB", (2550, 3300), "white")))


class ZoneTests(SimpleTestCase):
    def test_a_small_photo_zone_is_enlarged_to_a_scans_text_height(self):
        photo = Image.new("RGB", (856, 540), "white")
        zone = card_geometry.zone(photo, card_geometry.PID_ZONE)
        full = card_geometry.zone(Image.new("RGB", card_geometry.CARD_SIZE, "white"), card_geometry.PID_ZONE)
        self.assertAlmostEqual(zone.width, full.width, delta=3)
