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

**`pid` is deliberately NOT validated** (user decision, 2026-08-10). It is the "no land twice"
dedup key and the office's real records carry more than one length; a wrong guess here would
refuse a legitimate beneficiary, which is worse than accepting an odd-looking one.
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

VALIDATION_KEYS = (
    PHONE_CHARS,
    PHONE_LENGTH,
    BIRTH_FUTURE,
    BIRTH_TOO_OLD,
    STEP_END_BEFORE_START,
)

# Digits, plus the separators people actually type on a form. Anything else — a letter above all —
# is a typo or a note that does not belong in a dialable number.
_PHONE_ALLOWED = re.compile(r"^[0-9+\-\s()]+$")
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
