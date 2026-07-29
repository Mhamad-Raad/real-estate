"""Read a national ID card into draft client fields (§6.5).

Three findings from the accuracy spike drive the shape of this module:

1. **There is no Sorani (`ckb`) Tesseract model.** Upstream ships only `kmr` (Kurmanji, Latin
   script). The Arabic *script* model reads Sorani letters far better than `ara` does — 88% vs
   68% on clean text — so `Arabic` is the model, and combining it with `ara` is worse than either.
2. **Preprocessing hurt.** Thresholding a modern glossy card shredded the thin Arabic strokes and
   turned 10 good lines into 70 of noise. Raw first; cleanup is a fallback, not a pipeline stage.
3. **The MRZ is the trustworthy source.** It carries check digits, so its dates and document
   number verify themselves — unlike anything read off the printed side.

Nothing here writes to the database. Extraction produces a *draft* that a human confirms (§6.5),
and confirming never freezes the data: every field stays editable afterwards.
"""

import re
from dataclasses import dataclass, field

from . import mrz

# The Arabic script model, not `ara` — see the module docstring.
ARABIC_MODEL = "Arabic"
LATIN_MODEL = "eng"

# The card number is 12 digits and begins with the holder's birth year.
PID_PATTERN = r"\b(\d{12})\b"

# Front-side field order. The card carries TWO grandfather lines and position decides whose each
# is: the first follows the father, the second follows the mother. Parsing is positional because
# the *labels* OCR badly (`الإسح` for `الاسم`) while the values come through clean.
FRONT_FIELDS = (
    "given_name",
    "father_name",
    "father_grandfather",
    "surname",
    "mother_name",
    "mother_grandfather",
)

# Lines that are card furniture rather than data.
HEADING_HINTS = ("البطاقة", "كارت", "نيشتمان", "الوطنية", "REPUBLIC", "IRAQ")

# The sex line sits directly after the names and is also `label : value`. Without this, a name
# line the engine failed to read would let the sex value slide up into the mother's-father slot
# — every later field shifted onto the wrong name, silently. Recognising the value stops that,
# and the same tokens give a front-side reading of sex to cross-check the MRZ against.
SEX_VALUES = {
    "ذكر": "M", "ذگر": "M", "نێر": "M", "نير": "M",
    "أنثى": "F", "انثى": "F", "مێ": "F", "مي": "F",
}


@dataclass
class Field:
    """One drafted value plus how much it should be trusted."""

    value: str = ""
    confidence: int = 0
    source: str = ""  # "mrz" | "front" | "mrz+front"
    verified: bool = False  # a check digit or a cross-source agreement confirmed it

    @property
    def is_empty(self) -> bool:
        return not self.value


@dataclass
class IdCardDraft:
    """What the lawyer sees pre-filled beside the scan. Every field is editable."""

    pid: Field = field(default_factory=Field)
    full_name: Field = field(default_factory=Field)
    mother_full_name: Field = field(default_factory=Field)
    date_of_birth: Field = field(default_factory=Field)
    sex: Field = field(default_factory=Field)
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "fields": {
                name: {
                    "value": value.value,
                    "confidence": value.confidence,
                    "source": value.source,
                    "verified": value.verified,
                }
                for name, value in (
                    ("pid", self.pid),
                    ("full_name", self.full_name),
                    ("mother_full_name", self.mother_full_name),
                    ("date_of_birth", self.date_of_birth),
                    ("sex", self.sex),
                )
            },
            "warnings": self.warnings,
        }


# Marks OCR leaves clinging to a value — the colon is often doubled or misread as `+`, `-`, `.`
# Stripped from both ends; never from inside, where they could be part of a real value.
EDGE_NOISE = " \t+-.,:;،؛/\\|_*'\"«»()[]{}"


def _value_after_colon(line: str) -> str:
    """Card lines read `<arabic label> / <kurdish label> : <value>`.

    Real output is messier than that — `لآب /باوك :+ رعد` — so the separator is taken as the
    last colon on the line and the remainder is stripped of punctuation the engine invented.
    """
    for separator in (":", "："):
        if separator in line:
            return line.split(separator)[-1].strip(EDGE_NOISE).strip()
    return ""


def parse_front_fields(text: str) -> dict[str, str]:
    """Map the front's labelled lines onto names, by position.

    Only lines carrying a name-like value are numbered, so a heading, a stray mark or the sex
    line cannot shift every later field onto the wrong name. Values reaching the sex line mean
    the name block is finished.
    """
    values: dict[str, str] = {}
    index = 0
    for raw in text.splitlines():
        line = raw.strip()
        if not line or any(hint in line for hint in HEADING_HINTS):
            continue
        value = _value_after_colon(line)
        if not value or value.isdigit():
            continue
        if value in SEX_VALUES:
            values["sex"] = SEX_VALUES[value]
            break  # the names end here
        if index < len(FRONT_FIELDS):
            values[FRONT_FIELDS[index]] = value
            index += 1
    return values


def compose_full_name(parts: dict[str, str]) -> str:
    """Given name + father + father's father + surname, in the order the office writes it."""
    ordered = ("given_name", "father_name", "father_grandfather", "surname")
    return " ".join(parts[key] for key in ordered if parts.get(key))


def compose_mother_full_name(parts: dict[str, str]) -> str:
    """Mother's given name + HER father — the second grandfather line (§3.7 dedup key)."""
    ordered = ("mother_name", "mother_grandfather")
    return " ".join(parts[key] for key in ordered if parts.get(key))


def find_pid(text: str, *, prefer: str = "") -> str:
    """The card number, 12 digits.

    The front also carries a family number of the same shape, so page order alone can pick the
    wrong one. When the MRZ has been read, its value decides which candidate is the card number.
    """
    matches = re.findall(PID_PATTERN, text)
    if prefer:
        for candidate in matches:
            if candidate in prefer:
                return candidate
    return matches[0] if matches else ""


def build_draft(
    *,
    front_text: str,
    back_text: str,
    front_latin_text: str = "",
    pid_confidence: int = 0,
    name_confidence: int = 0,
) -> IdCardDraft:
    """Combine both sides into one draft.

    The PID is the highest-stakes field on the card: it is the key behind the "no land twice"
    unique index, so a misread either blocks a legitimate applicant or admits a duplicate. It
    appears both printed on the front and inside the MRZ, and agreement between those two
    independent reads is treated as the strongest signal available.
    """
    draft = IdCardDraft()
    zone = mrz.parse(back_text)

    # The national ID sits in the MRZ optional-data field; `document_number` is the card serial.
    mrz_pid = zone.national_id
    # The card number is Latin digits, which the Arabic model garbles (`240M 01`); look for it
    # in the Latin pass first and fall back to the Arabic one.
    front_pid = find_pid(front_latin_text, prefer=mrz_pid) or find_pid(front_text, prefer=mrz_pid)

    if front_pid and mrz_pid and front_pid in mrz_pid:
        draft.pid = Field(front_pid, max(pid_confidence, 95), "mrz+front", verified=True)
    elif front_pid and mrz_pid:
        draft.pid = Field(front_pid, min(pid_confidence, 60), "front")
        draft.warnings.append(
            f"The card number printed on the front ({front_pid}) does not match the one in the "
            f"machine-readable zone ({mrz_pid}). Check both before saving."
        )
    elif front_pid:
        draft.pid = Field(front_pid, pid_confidence, "front")
    elif mrz_pid:
        draft.pid = Field(mrz_pid, 70, "mrz")

    parts = parse_front_fields(front_text)
    if full_name := compose_full_name(parts):
        draft.full_name = Field(full_name, name_confidence, "front")
    if mother := compose_mother_full_name(parts):
        draft.mother_full_name = Field(mother, name_confidence, "front")
    if not parts.get("mother_grandfather"):
        draft.warnings.append(
            "Could not read the mother's father from the card, so her full name may be "
            "incomplete. It is used to detect duplicate applicants — please check it."
        )

    if zone.date_of_birth:
        verified = "date_of_birth" in zone.verified
        draft.date_of_birth = Field(
            zone.date_of_birth.isoformat(), 95 if verified else 60, "mrz", verified=verified
        )
    front_sex = parts.get("sex", "")
    if zone.sex and front_sex:
        agrees = zone.sex == front_sex
        draft.sex = Field(zone.sex, 95 if agrees else 50, "mrz+front", verified=agrees)
        if not agrees:
            draft.warnings.append("The sex on the front of the card disagrees with the MRZ.")
    elif zone.sex or front_sex:
        draft.sex = Field(zone.sex or front_sex, 75, "mrz" if zone.sex else "front")

    if not zone.is_usable:
        draft.warnings.append(
            "The machine-readable zone on the back of the card could not be read or did not "
            "pass its check digits. Dates and the card number need checking by eye."
        )
    _warn_about_empty_fields(draft)
    return draft


# What each field is called when the reader has to admit it could not get one.
FIELD_LABELS = {
    "pid": "the card number",
    "full_name": "the full name",
    "mother_full_name": "the mother's full name",
    "date_of_birth": "the date of birth",
}


def _warn_about_empty_fields(draft: IdCardDraft) -> None:
    """Say so when a field could not be read, instead of leaving a silent blank box.

    Partial failure is the normal case on a photocopy and it used to pass unremarked: a single
    copier pass breaks the birth date's check digit while the document number still verifies, so
    `is_usable` stayed true, the MRZ warning never fired, and the lawyer was shown an empty
    required field with no reason for it. An unexplained blank invites the assumption that the
    card simply did not carry the value (§6.2, §6.5).
    """
    unread = [
        FIELD_LABELS[name]
        for name in ("pid", "full_name", "mother_full_name", "date_of_birth")
        if getattr(draft, name).is_empty
    ]
    if not unread:
        return
    fields = unread[0] if len(unread) == 1 else ", ".join(unread[:-1]) + f" and {unread[-1]}"
    draft.warnings.append(
        f"Could not read {fields} from the card — please enter {'it' if len(unread) == 1 else 'them'} "
        f"by hand. This usually means the scan is a photocopy or is too low in quality."
    )
