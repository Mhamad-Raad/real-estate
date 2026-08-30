"""Reusable field validators for the domain serializers (§4.1).

These exist because the API accepted, and **stored**, values a human never typed on purpose: a
phone of `"hello world"`, a birth date in the year 2099, another in 1300. Nothing rejected them,
so the bad value reached the database and then the printed letter.

They live here rather than on the models deliberately. The office's existing rows predate every
rule below — a national ID typed years ago cannot be made to pass a check invented today — and a
**model** validator would fire on every save of an untouched field, so correcting someone's phone
number would demand fixing their birth date first. A **serializer** field validator only runs on
what the request actually writes, which is the rule the user chose: validate what is being
written, leave the rest alone.

**`pid` was deliberately NOT validated** (user decision, 2026-08-10) — **reversed 2026-08-20**, at
the office's request: exactly **12 digits**. The original reasoning still holds for the records
they already have, which is why the rule fires only on a PID being **set or changed** and never on
one merely carried along by an edit to some other field. See `validate_pid`.
"""

import re
from datetime import date

from rest_framework import serializers

# The messages are **i18n keys**, not English sentences. The office reads these screens in Sorani
# (§9), and a validation error is the most routine thing a user ever sees — answering it in
# English makes it barely more useful than the silent failure it replaced. Same precedent as the
# institute and document-type vocabularies: the server sends a stable machine key, the frontend
# renders the language. `common.test_validation_keys` pins that every key here has a translation,
# so one can never reach a user as a raw dotted string.
#
# Deliberately parameterless: the bounds below are constants, so `10–11` and `1900` live in the
# translation rather than travelling as interpolation values through DRF's string-only error shape.
PHONE_CHARS = "errors.phone.chars"
PHONE_LENGTH = "errors.phone.length"
BIRTH_FUTURE = "errors.birthDate.future"
BIRTH_TOO_OLD = "errors.birthDate.tooOld"
STEP_END_BEFORE_START = "errors.stepDate.endBeforeStart"
# Refusing a document a slot has no room for (UC-085). Not a field validator — the rule lives in
# `documents.services` — but its message is one more thing the API says to the office, so it is
# registered here with the rest and covered by the same translation guard.
SLOT_SIDES_FULL = "errors.slot.sidesFull"
SLOT_PAGES_FULL = "errors.slot.pagesFull"
SLOT_FILES_FULL = "errors.slot.filesFull"
PID_FORMAT = "errors.pid.format"

VALIDATION_KEYS = (
    PHONE_CHARS,
    PHONE_LENGTH,
    BIRTH_FUTURE,
    BIRTH_TOO_OLD,
    STEP_END_BEFORE_START,
    SLOT_SIDES_FULL,
    SLOT_PAGES_FULL,
    SLOT_FILES_FULL,
    PID_FORMAT,
)

# Digits, plus the separators people actually type on a form. **The dash is not one of them**
# (user decision, 2026-08-11). Anything else — a letter above all — is a typo or a note that does
# not belong in a dialable number. Kept in step with `frontend/src/lib/phone.ts`, which refuses the
# same characters at the keystroke; if the two drift, the box and the API disagree about one field.
#
# **Arabic-Indic digits count as digits.** This office's whole world is written in them — the
# generated letters render every number through `to_arabic_indic`, the ID cards OCR reads carry
# them, and the screens format them with `useNum`. An ASCII-only rule told a lawyer who had typed
# `٠٧٧٠١٢٣٤٥٦٧` that the field "may contain only digits", which is both wrong and baffling, since
# digits are exactly what they typed. `\d` already matches them when counting; only the character
# gate was ASCII. U+0660–0669 is Arabic-Indic, U+06F0–06F9 the Extended (Persian) form.
_PHONE_ALLOWED = re.compile(r"^[0-9٠-٩۰-۹+\s()]+$")
_DIGITS = re.compile(r"\d")

# The office's own numbers are 10 or 11 digits (measured across their live rows: `07XXXXXXXXX`,
# and the same without the leading zero).
PHONE_MIN_DIGITS = 10
PHONE_MAX_DIGITS = 11
# A country code is not part of the national number, so it is removed before counting — otherwise
# `+964 770 123 4567` is 13 digits and would be refused for being too long. Its length is not
# assumed: whichever leading 1–3 digits leave a valid national number behind is the country code.
MAX_COUNTRY_CODE_DIGITS = 3


def _national_digits(value: str) -> str:
    """The dialable digits with any leading country code removed."""
    digits = "".join(_DIGITS.findall(value))
    if not value.lstrip().startswith("+"):
        return digits
    for cc in range(1, MAX_COUNTRY_CODE_DIGITS + 1):
        if PHONE_MIN_DIGITS <= len(digits) - cc <= PHONE_MAX_DIGITS:
            return digits[cc:]
    return digits

# Nobody alive is older than this. A lower bound is what catches a mistyped century — `1300` for
# `1980` — which is otherwise a perfectly well-formed date.
EARLIEST_BIRTH_YEAR = 1900


def validate_phone(value: str) -> str:
    """A dialable number: digits and separators only, 10–11 digits (user decision, 2026-08-10)."""
    if not value:
        return value  # blank is allowed; the field is optional
    if not _PHONE_ALLOWED.match(value):
        raise serializers.ValidationError(PHONE_CHARS)
    digits = len(_national_digits(value))
    if not PHONE_MIN_DIGITS <= digits <= PHONE_MAX_DIGITS:
        raise serializers.ValidationError(PHONE_LENGTH)
    return value


def validate_birth_date(value: date | None) -> date | None:
    """A birth date that could belong to a living applicant.

    Both ends matter and for different reasons: a **future** date is impossible and was being
    accepted outright, while an absurdly old one is how a mistyped century arrives — it parses,
    it stores, and it prints on a government letter as a 700-year-old beneficiary.
    """
    if value is None:
        return value
    if value > date.today():
        raise serializers.ValidationError(BIRTH_FUTURE)
    if value.year < EARLIEST_BIRTH_YEAR:
        raise serializers.ValidationError(BIRTH_TOO_OLD)
    return value


# The national ID is exactly this many digits — the office's own rule (2026-08-20). Leading and
# trailing zeros are ordinary, which is the whole reason `pid` is a string and never an integer:
# `007…` and `…000` must survive a round trip unchanged.
# A **maximum**, not a length (the office, 2026-08-30). It was exactly 12 for ten days — see
# `validate_pid` for why that had to give.
PID_MAX_DIGITS = 12

# Arabic-Indic and Persian digits, mapped to ASCII. The office types numbers in their own script
# everywhere (§9), so refusing `١٩٩٠…` would refuse a correctly-entered ID — but the PID is the
# "no land twice" dedup key (§5.7), and `١٩٩٠` and `1990` are *different strings* to an index.
# Accepting both without folding them would open a duplicate straight through the guard, so the
# stored value is always ASCII.
_DIGIT_FOLD = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def normalise_pid(value: str) -> str:
    """The canonical form of a PID: Arabic-Indic digits folded to ASCII, surrounding space gone."""
    return (value or "").strip().translate(_DIGIT_FOLD)


def validate_pid(value: str) -> str:
    """Digits only, **at most** `PID_MAX_DIGITS` of them, in canonical ASCII form.

    **A maximum since 2026-08-30**, where the office's 2026-08-20 rule said *exactly* twelve. Their
    own records were always the argument against exactness — 15 rows of 9 digits against 6 of 12
    when it was measured — and the paper backlog (§5.9) is thousands more of the same: a rule that
    refuses a 9-digit ID refuses the card the lawyer is holding. What the rule still buys is the
    part that was always the point: **digits, folded to ASCII, and no more than twelve** — so a
    letter, a `DEMO-` string or a mistyped run of fifteen is still caught.

    **Applied to a PID being set or changed, never to one an edit merely carries along.** The
    client form submits the whole record, so validating unconditionally would fail a phone
    correction on a PID nobody touched.
    """
    pid = normalise_pid(value)
    if not pid or len(pid) > PID_MAX_DIGITS or not pid.isdigit() or not pid.isascii():
        raise serializers.ValidationError(PID_FORMAT)
    return pid
