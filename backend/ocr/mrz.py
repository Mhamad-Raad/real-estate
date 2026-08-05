"""ICAO 9303 machine-readable zone parsing (§6.5).

The MRZ on the back of the national ID is the most reliable thing on the card: it is designed to
be machine-read and it carries **check digits**, so a misread can be *detected* rather than
merely hoped about. Everything here is pure — bytes in, dataclass out — so it unit-tests without
Tesseract, a database or a file.
"""

from dataclasses import dataclass, field
from datetime import date

# Filler character and the weights ICAO applies to each position in a checked run.
FILLER = "<"
WEIGHTS = (7, 3, 1)


def char_value(ch: str) -> int:
    if ch.isdigit():
        return int(ch)
    if ch == FILLER:
        return 0
    return ord(ch.upper()) - 55  # A=10 … Z=35


def check_digit(sequence: str) -> str:
    total = sum(char_value(ch) * WEIGHTS[i % 3] for i, ch in enumerate(sequence))
    return str(total % 10)


def verify(sequence: str, expected: str) -> bool:
    """A check digit the card does not carry (filler) cannot verify anything."""
    return expected.isdigit() and check_digit(sequence) == expected


def parse_yymmdd(value: str, *, century_pivot: int = 30) -> date | None:
    """`010812` → 2001-08-12.

    The MRZ stores a two-digit year, so the century has to be inferred. A birth date on a national
    ID is always in the past: years above the pivot are 19xx, at or below are 20xx — and anything
    the pivot still lands in the future is pulled back a century, since the direction of the field
    is the more reliable rule.
    """
    if len(value) != 6 or not value.isdigit():
        return None
    yy, mm, dd = int(value[0:2]), int(value[2:4]), int(value[4:6])
    year = 1900 + yy if yy > century_pivot else 2000 + yy
    try:
        parsed = date(year, mm, dd)
    except ValueError:  # OCR can produce month 00 or day 32
        return None
    if parsed > date.today():
        parsed = parsed.replace(year=parsed.year - 100)
    return parsed


@dataclass
class MrzResult:
    # The card's own serial (letter + digits), NOT the national ID.
    document_number: str = ""
    # TD1 line 1 carries an optional-data field after the document number. On the KRG/Iraqi card
    # this is where the **national ID** lives — the number the office uses as `pid`.
    national_id: str = ""
    date_of_birth: date | None = None
    sex: str = ""
    nationality: str = ""
    surname: str = ""
    given_names: str = ""
    # Which fields carried a check digit that actually verified.
    verified: set[str] = field(default_factory=set)
    lines: list[str] = field(default_factory=list)

    @property
    def is_usable(self) -> bool:
        """At least one checked field must verify before any of this is worth trusting."""
        return bool(self.verified)


def find_mrz_lines(text: str) -> list[str]:
    """Pull the MRZ out of a full-page OCR dump.

    Identified by shape rather than position: MRZ lines are dense runs of A–Z, digits and `<`.
    Spaces are stripped because OCR sprinkles them through the filler runs.
    """
    candidates = []
    for raw in text.splitlines():
        line = "".join(raw.split()).upper()
        if len(line) >= 25 and line.count(FILLER) >= 3:
            # Drop anything that is not part of the MRZ alphabet (stray marks, Arabic bleed).
            candidates.append("".join(ch for ch in line if ch.isalnum() or ch == FILLER))
    return candidates


# Letters the engine routinely substitutes for digits. Applied ONLY to fields the standard says
# are numeric — dates and check digits — never to the document number, which really can contain
# letters. The office's own card read `9SO1016` for `9501016`, which cost the date of birth and
# its check digit, and so the whole MRZ was reported unverified (UC-068).
OCR_DIGIT_FIXES = str.maketrans({"O": "0", "Q": "0", "D": "0", "I": "1", "L": "1", "Z": "2",
                                 "S": "5", "G": "6", "B": "8"})


def as_digits(raw: str) -> str:
    """A numeric MRZ field with the usual OCR letter-for-digit substitutions undone."""
    return raw.translate(OCR_DIGIT_FIXES)


def parse_td1(lines: list[str]) -> MrzResult:
    """Parse a TD1 (three-line, 30-character) MRZ — the format used by ID cards.

    Tolerant of length drift: OCR routinely loses or invents trailing filler, so fields are read
    by offset from the start of each line and validated by their check digits instead.
    """
    result = MrzResult(lines=lines)
    if len(lines) < 2:
        return result

    first, second = lines[0], lines[1]

    # Line 1: doc code (2) + issuer (3) + document number (9) + check digit + optional data (15).
    if len(first) >= 15:
        number = first[5:14]
        result.document_number = number.replace(FILLER, "")
        # The number itself may legitimately contain letters; its check digit may not.
        if verify(number, as_digits(first[14:15])):
            result.verified.add("document_number")
        # The optional-data field holds the national ID on this card. It carries no check digit
        # of its own here, so it is cross-checked against the front of the card instead.
        result.national_id = "".join(ch for ch in first[15:] if ch.isdigit())

    # Line 2: birth date (6) + check, sex (1), expiry (6) + check, nationality (3).
    # The expiry date is read past, not parsed: the office cares who the holder is, not whether
    # the card is still in date, and a national ID does not stop identifying its holder when it
    # expires. Its offsets still matter, because nationality sits after it.
    if len(second) >= 15:
        # Both are numeric by the standard, so an OCR letter here is a misread, not data.
        dob_raw, dob_cd = as_digits(second[0:6]), as_digits(second[6:7])
        result.date_of_birth = parse_yymmdd(dob_raw)
        if result.date_of_birth and verify(dob_raw, dob_cd):
            result.verified.add("date_of_birth")

        sex = second[7:8]
        result.sex = sex if sex in ("M", "F") else ""

        result.nationality = second[15:18].replace(FILLER, "")

    # Line 3: SURNAME<<GIVEN<NAMES, padded with filler.
    if len(lines) >= 3:
        surname, _, given = lines[2].partition(FILLER * 2)
        result.surname = surname.replace(FILLER, " ").strip()
        result.given_names = " ".join(given.replace(FILLER, " ").split())

    return result


def parse(text: str) -> MrzResult:
    """Find and parse the MRZ in a page of OCR text.

    The last three candidates are the zone: it sits at the bottom of the card, so anything else
    dense enough to look like MRZ (a printed serial, Arabic bleed) is above it. Taking the first
    three instead let one stray line shift every field and lose the whole read.
    """
    return parse_td1(find_mrz_lines(text)[-3:])
