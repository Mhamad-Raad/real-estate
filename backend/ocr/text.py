"""Arabic-script text comparison shared by the name parser and the accuracy bench (UC-126)."""

import re
import unicodedata

# Letters the card prints and the engine returns in interchangeable forms: Arabic and Persian yeh
# and kaf, heh and the Kurdish ae, alef with and without hamza. A reader treats them as the same
# name, so neither the parser nor the bench should treat a difference here as a different word.
FOLD = str.maketrans(
    {
        "ی": "ي", "ى": "ي", "ئ": "ي", "ک": "ك", "ە": "ه", "ة": "ه", "ۀ": "ه",
        "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا",
        "ـ": "", "‌": "", "‍": "",  # tatweel and zero-width joiners
    }
)


def normalise_name(value: str) -> str:
    """Fold letter variants and collapse whitespace, so only real differences remain."""
    value = unicodedata.normalize("NFKC", value or "").translate(FOLD)
    return re.sub(r"\s+", " ", value).strip()


def similarity(a: str, b: str) -> float:
    """1 − edit distance ÷ the longer length. 1.0 is identical, 0.0 shares nothing."""
    if a == b:
        return 1.0
    if not a or not b:
        return 0.0
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return 1 - previous[-1] / max(len(a), len(b))

