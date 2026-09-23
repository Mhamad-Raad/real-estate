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
from collections import Counter
from dataclasses import dataclass, field

from . import mrz
from .text import normalise_name, similarity

# The Arabic script model, not `ara` — see the module docstring.
ARABIC_MODEL = "Arabic"
LATIN_MODEL = "eng"

# The card number is 12 digits and begins with the holder's birth year.
#
# **Still exactly 12 here, even though `validate_pid` now accepts fewer** (UC-115). The two answer
# different questions: the validator asks "may a person type this?", and the office's older records
# hold 9-digit IDs; this asks "which run of digits on a **modern card** is the number?" — and the
# front of that card also carries a **family number of the same shape** (§6.2). Loosening this to
# `\d{9,12}` would not read old cards better; it would start proposing the family number, other
# short runs, and fragments, on the door where a wrong PID creates a false duplicate or a false new
# person. An old card simply falls through to manual entry, which is always open (§6.5).
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

# The printed labels, folded, per slot — Arabic first, then Kurdish. Labels OCR worse than values,
# so they are only used as anchors when they match well; the grandfather label appears twice and
# its slot is decided by where the parse already is.
LABEL_SLOTS = (
    (0, ("الاسم", "ناو")),
    (1, ("الاب", "باوك")),
    ("grandfather", ("الجد", "بابير")),
    (3, ("اللقب", "نازناو")),
    (4, ("الام", "دايك")),
    ("sex", ("الجنس", "رهگهز")),
)
LABEL_MATCH = 0.75

# Lines that are card furniture rather than data.
HEADING_HINTS = (
    "البطاقة", "كارت", "نيشتمان", "الوطنية", "REPUBLIC", "IRAQ",
    # The ministry and directorate headings, which share words with the labels (UC-126).
    "جمهورية", "وزارة", "مديرية", "العراق", "عيراق", "الداخلية", "الجنسية", "الاحوال", "فصيلة",
)

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


def label_slot(label_text: str, index: int):
    """Which row a line's printed label names, or None when the label is not legible enough.

    Only forward moves are accepted: `الاب` and `الام` differ by one letter, and a label that would
    send the parse backwards is a misread, not a row.
    """
    # Labels are whole words. Matching inside words found "ناو" in the ministry's "ناوخۆ" and
    # "الجنس" in "الجنسية", which ended the name block on the card's heading.
    tokens = [t for t in re.split(r"[\s/|:()\[\].،]+", normalise_name(label_text)) if t]
    best_score, best_slot = 0.0, None
    for slot, spellings in LABEL_SLOTS:
        # A three-letter Kurdish label matches too much by accident, so short spellings must be exact.
        score = max(
            (similarity(token, spelling) if len(spelling) > 3 else float(token == spelling))
            for spelling in spellings
            for token in tokens
        ) if tokens else 0.0
        if slot == "grandfather":
            slot = 2 if index <= 2 else 5
        if score >= LABEL_MATCH and score > best_score and (slot == "sex" or slot >= index):
            best_score, best_slot = score, slot
    return best_slot


def parse_front_fields(text: str) -> dict[str, str]:
    """Map the front's labelled lines onto names — by label where it is legible, else by position.

    Only lines carrying a name-like value are numbered, so a heading, a stray mark or the sex
    line cannot shift every later field onto the wrong name. Values reaching the sex line mean
    the name block is finished.

    **A row with no value still holds its place when its label is legible (UC-126).** The surname
    row is blank on most KRG cards; skipping it moved the mother's name into the surname slot and
    her father into the mother's, on every such card in the scored sample set.
    """
    values: dict[str, str] = {}
    index = 0
    for raw in text.splitlines():
        line = raw.strip()
        if not line or any(hint in line for hint in HEADING_HINTS):
            continue
        value = _value_after_colon(line)
        label_part = line.rsplit(":", 1)[0] if ":" in line else line
        slot = label_slot(label_part, index)
        if slot == "sex":
            if value in SEX_VALUES:
                values["sex"] = SEX_VALUES[value]
            break
        if slot is not None:
            index = slot
        if not value or value.isdigit():
            if slot is not None:
                index = slot + 1  # a legible label with nothing after it: that row is empty
            continue
        if value in SEX_VALUES:
            values["sex"] = SEX_VALUES[value]
            break  # the names end here
        if index < len(FRONT_FIELDS):
            values[FRONT_FIELDS[index]] = value
            index += 1
    return values


# The name block is read **positionally** — the first name-like line is the given name, the second
# the father, and so on. That only holds while the block is read coherently. A card these fields
# are unreadable on may yield a single surviving line, and position alone then declares it the
# applicant's given name: on the office's own scan the only legible line was the MOTHER's, and it
# was offered as the applicant (UC-068). Below this many lines the positions mean nothing, so no
# name is proposed at all — an empty box asks the lawyer to type it, a wrong one invites them to
# accept it, and the invariant is that OCR never gets trusted blindly (§6.5).
MIN_NAME_LINES_FOR_POSITIONS = 3


def positions_are_trustworthy(parts: dict[str, str]) -> bool:
    """Did enough of the name block survive for its ordering to mean anything?"""
    return len([key for key in FRONT_FIELDS if parts.get(key)]) >= MIN_NAME_LINES_FOR_POSITIONS


def compose_full_name(parts: dict[str, str]) -> str:
    """Given name + father + father's father + surname, in the order the office writes it."""
    if not positions_are_trustworthy(parts):
        return ""
    ordered = ("given_name", "father_name", "father_grandfather", "surname")
    return " ".join(parts[key] for key in ordered if parts.get(key))


def compose_mother_full_name(parts: dict[str, str]) -> str:
    """Mother's given name + HER father — the second grandfather line (§3.7 dedup key)."""
    if not positions_are_trustworthy(parts):
        return ""
    ordered = ("mother_name", "mother_grandfather")
    return " ".join(parts[key] for key in ordered if parts.get(key))


def find_pid(text: str, *, prefer: str = "", birth_year_yy: str = "") -> str:
    """The card number, 12 digits.

    The front also carries a family number of the same shape, so page order alone can pick the
    wrong one. When the MRZ has been read, its value decides which candidate is the card number;
    failing that, a verified birth year does, since the number starts with it.
    """
    matches = re.findall(PID_PATTERN, text or "")
    if prefer:
        for candidate in matches:
            if candidate in prefer:
                return candidate
    if birth_year_yy:
        for candidate in matches:
            if candidate[:2] in ("19", "20") and candidate[2:4] == birth_year_yy:
                return candidate
    return matches[0] if matches else ""


def reconcile_pid_with_birth_year(pid: str, birth_year_yy: str) -> str:
    """The card number starts with the holder's four-digit birth year (§6.2).

    With the birth date verified by its check digit, that prefix becomes checkable. One repair is
    allowed, the engine's commonest misread on this font: the leading `1` of `19xx` (or `2` of
    `20xx`) read as another digit, as in `497120937030` for `197120937030` (UC-126). It changes
    only the century digit the verified date implies, never a digit the date cannot vouch for.
    """
    if not pid or len(pid) != 12 or pid[2:4] != birth_year_yy:
        return pid
    if pid[:2] in ("19", "20"):
        return pid
    if pid[1] == "9":
        return "1" + pid[1:]
    if pid[1] == "0":
        return "2" + pid[1:]
    return pid


def pid_votes(texts, birth_year_yy: str = "") -> "Counter[str]":
    """Every 12-digit card number the reads contain, counted once per read that contains it.

    An MRZ read can carry a check digit or a stray character around the number, so each 12-digit
    window of a longer run counts as a candidate — but only a window that starts with a plausible
    birth year, and at half the weight of a clean 12-digit read, since the run it came from is
    already known to hold a wrong or extra character.
    """
    votes: Counter[str] = Counter()
    for text in texts:
        found: dict[str, int] = {}
        for run in re.findall(r"\d{12,}", text or ""):
            windows = [run] if len(run) == 12 else [run[i : i + 12] for i in range(len(run) - 11)]
            for window in windows:
                window = reconcile_pid_with_birth_year(window, birth_year_yy)
                if len(run) == 12:
                    found[window] = 2
                elif window[:2] in ("19", "20"):
                    found.setdefault(window, 1)
        votes.update(found)
    return votes


def best_vote(votes: "Counter[str]", birth_year_yy: str = "") -> str:
    """Most votes wins; a number starting with the verified birth year beats one that does not."""
    if not votes:
        return ""

    def rank(pid: str):
        plausible = pid[:2] in ("19", "20")
        year_match = bool(birth_year_yy) and pid[2:4] == birth_year_yy
        return (year_match, votes[pid], plausible)

    return max(votes, key=rank)


def build_draft(
    *,
    front_text: str,
    back_text: str,
    front_latin_text: str = "",
    pid_confidence: int = 0,
    name_confidence: int = 0,
    extra_back_texts: tuple[str, ...] = (),
    extra_pid_texts: tuple[str, ...] = (),
) -> IdCardDraft:
    """Combine both sides into one draft.

    The PID is the highest-stakes field on the card: it is the key behind the "no land twice"
    unique index, so a misread either blocks a legitimate applicant or admits a duplicate. It
    appears both printed on the front and inside the MRZ, and agreement between those two
    independent reads is treated as the strongest signal available.
    """
    draft = IdCardDraft()
    # Every read of the back competes; check digits pick the winner (UC-126).
    back_reads = [mrz.parse(text) for text in (back_text, *extra_back_texts) if text]
    zone = mrz.parse_best([back_text, *extra_back_texts])
    dob_verified = bool(zone.date_of_birth) and "date_of_birth" in zone.verified
    birth_yy = f"{zone.date_of_birth.year % 100:02d}" if dob_verified else ""

    # The card number is Latin digits, which the Arabic model garbles (`240M 01`); every read that
    # could hold it votes — the zone read, the Latin pass, the Arabic pass, and each MRZ read.
    front_votes = pid_votes((*extra_pid_texts, front_latin_text, front_text), birth_yy)
    mrz_votes = pid_votes([read.national_id for read in back_reads], birth_yy)
    agreed = [pid for pid in front_votes if pid in mrz_votes]
    front_pid = best_vote(front_votes, birth_yy)
    mrz_pid = best_vote(mrz_votes, birth_yy)

    if agreed:
        pid = max(agreed, key=lambda value: front_votes[value] + mrz_votes[value])
        draft.pid = Field(pid, max(pid_confidence, 95), "mrz+front", verified=True)
    elif front_pid and mrz_pid:
        # The two sides disagree. The MRZ's machine-reading font wins only when it is the number the
        # verified birth year vouches for and the front's is not; either way the lawyer is told.
        mrz_wins = bool(birth_yy) and mrz_pid[2:4] == birth_yy and front_pid[2:4] != birth_yy
        chosen = mrz_pid if mrz_wins or mrz_votes[mrz_pid] > front_votes[front_pid] else front_pid
        draft.pid = Field(chosen, min(pid_confidence or 60, 60), "mrz" if chosen == mrz_pid else "front")
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
        born = zone.date_of_birth
        # The MRZ carries a two-digit year; a verified card number carries all four. `000701` is
        # 1900-07-01 on a card numbered `1900…`, not 2000-07-01 (UC-126).
        if verified and draft.pid.value[:2] in ("19", "20") and draft.pid.value[2:4] == f"{born.year % 100:02d}":
            century_year = int(draft.pid.value[:4])
            if century_year != born.year:
                try:
                    born = born.replace(year=century_year)
                except ValueError:  # 29 February in a year that has none: keep the MRZ reading
                    pass
        draft.date_of_birth = Field(born.isoformat(), 95 if verified else 60, "mrz", verified=verified)
    if dob_verified and draft.pid.value and draft.pid.value[2:4] != birth_yy:
        draft.pid.confidence = min(draft.pid.confidence, 40)
        draft.pid.verified = False
        draft.warnings.append(
            f"The card number {draft.pid.value} does not start with the birth year on the card. "
            "Check the number carefully before saving."
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
