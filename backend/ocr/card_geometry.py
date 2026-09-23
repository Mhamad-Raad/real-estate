"""Where the card is, and where each field sits on it (§6.2, UC-126).

Image arithmetic only — no Tesseract, no files — so the geometry is testable on a drawn image.

Measured on the office's own scans: a sheet from the flatbed is 2550×3300 px with the card a
~1011×638 px island somewhere on it, often tilted, sometimes on crumpled paper with handwriting
beside it. Reading that page whole returned **no text at all** and took ~14 s. Finding the card,
straightening it and reading its zones took the card number from 3/6 to 6/6 on those scans, and
the read from ~14 s to ~10 s. A photograph or a camera capture is already the card and is passed
through untouched.
"""

from __future__ import annotations

# ID-1 card: 85.60 × 53.98 mm.
CARD_RATIO = 85.6 / 53.98
# A straightened card is drawn at 20 px/mm: enough for the name strokes, cheap enough to read.
CARD_SIZE = (1712, 1080)

# Below this long edge an image is a photo or a capture of the card itself, not a scanned sheet.
MIN_SHEET_LONG_EDGE = 1800
# A letter sheet is 11 in and A4 11.69 in on its long edge; the midpoint is within 3% of both, which
# lets the page's own pixel size say how large a card on it has to be.
SHEET_LONG_EDGE_INCHES = 11.35
CARD_LONG_EDGE_INCHES = 3.370

# Zones as (left, top, right, bottom) fractions of a straightened card.
PID_ZONE = (0.28, 0.20, 0.70, 0.40)  # the 12-digit card number under the "national card" heading
MRZ_ZONE = (0.00, 0.52, 1.00, 0.97)  # the three machine-readable lines on the back


def find_card_on_sheet(image):
    """The card's rotated rectangle on a scanned sheet, or None when the image is not a sheet.

    The card is the only blue-tinted object on white paper, but it can touch another sheet's edge
    or a second card, which merges it into a larger blob. So the mask is eroded step by step until a
    piece of the right *physical size* separates, and that piece's centre and angle are kept.
    """
    import cv2
    import numpy as np

    width, height = image.size
    longest = max(width, height)
    if longest < MIN_SHEET_LONG_EDGE:
        return None
    expected_long = longest / SHEET_LONG_EDGE_INCHES * CARD_LONG_EDGE_INCHES
    expected_short = expected_long / CARD_RATIO

    hsv = cv2.cvtColor(np.asarray(image.convert("RGB")), cv2.COLOR_RGB2HSV)
    hue, sat, val = cv2.split(hsv)
    mask = ((sat > 18) & (hue >= 70) & (hue <= 150) & (val > 90)).astype(np.uint8) * 255
    kernel_size = max(3, min(width, height) // 60)
    kernel = np.ones((kernel_size, kernel_size), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    best_error, best_rect = 0.25, None
    for iteration in range(10):
        eroded = cv2.erode(mask, kernel, iterations=iteration) if iteration else mask
        contours, _ = cv2.findContours(eroded, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            centre, (w, h), angle = cv2.minAreaRect(contour)
            # Add back what the erosion took off each side before comparing sizes.
            grown = iteration * (kernel_size - 1)
            long_side, short_side = max(w, h) + grown, min(w, h) + grown
            error = abs(long_side - expected_long) / expected_long + abs(short_side - expected_short) / expected_short
            if error < best_error:
                size = (expected_long, expected_short) if w >= h else (expected_short, expected_long)
                best_error, best_rect = error, (centre, size, angle)
        if best_rect is not None and best_error < 0.08:
            break
    return best_rect


def straighten(image, rect):
    """Cut the rotated rectangle out of the page and draw it upright at `CARD_SIZE`."""
    import cv2
    import numpy as np
    from PIL import Image

    corners = cv2.boxPoints(rect)
    sums, diffs = corners.sum(axis=1), np.diff(corners, axis=1).ravel()
    top_left, bottom_right = corners[np.argmin(sums)], corners[np.argmax(sums)]
    top_right, bottom_left = corners[np.argmin(diffs)], corners[np.argmax(diffs)]
    source = np.array([top_left, top_right, bottom_right, bottom_left], dtype=np.float32)
    # A rectangle found standing up is a card lying on its long side: turn the corners a quarter.
    if np.linalg.norm(bottom_left - top_left) > np.linalg.norm(top_right - top_left):
        source = np.array([bottom_left, top_left, top_right, bottom_right], dtype=np.float32)
    width, height = CARD_SIZE
    target = np.array([[0, 0], [width, 0], [width, height], [0, height]], dtype=np.float32)
    matrix = cv2.getPerspectiveTransform(source, target)
    pixels = np.asarray(image.convert("RGB"))
    return Image.fromarray(cv2.warpPerspective(pixels, matrix, CARD_SIZE, flags=cv2.INTER_CUBIC))


def card_image(image):
    """The card to read: straightened out of a scanned sheet, or the image itself when it already is
    the card. Returns `(image, found_on_sheet)`."""
    # Test doubles hand in placeholders, not images; a real image always has `convert`.
    if not hasattr(image, "convert"):
        return image, False
    rect = find_card_on_sheet(image)
    if rect is None:
        return image, False
    return straighten(image, rect), True


def zone(card, box, *, card_width: int = CARD_SIZE[0]):
    """Crop a zone, scaled as if the card were `card_width` wide, so a small photo's zone is read at
    the same text height as a scan's."""
    from PIL import Image

    width, height = card.size
    left, top, right, bottom = box
    cropped = card.crop((round(left * width), round(top * height), round(right * width), round(bottom * height)))
    scale = card_width / width
    if abs(scale - 1) < 0.05:
        return cropped
    return cropped.resize((max(1, round(cropped.width * scale)), max(1, round(cropped.height * scale))), Image.LANCZOS)
