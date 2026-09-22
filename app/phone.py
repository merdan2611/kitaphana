"""Phone number normalisation (Sprint 03 task 1, ADR-0006).

Every path that accepts a phone number goes through `normalize_phone`: sign-up, login, the
admin script, and in Phase 2 the payment webhook. If one person can reach two accounts, or a
payment cannot find the account that made it, the bug is here.

Canonical form: `+993` followed by eight digits, e.g. `+99361234567`.
"""
from __future__ import annotations

import re

# Spaces, dashes, brackets and dots are how people group digits; they carry no meaning.
_SEPARATORS = re.compile(r"[\s\-().]")
# [0-9], not \d: \d also matches Arabic-Indic and other Unicode digits.
_DIGITS = re.compile(r"[0-9]+")
# Turkmen mobile numbers start with 6X (TMCELL 61-65, MTS 66-68 and so on) or 71. Deliberately
# broad: turning away a real reader costs more than accepting an unassigned prefix, which
# can still never receive a code. Landlines (Ashgabat 12, regional 1X-5X) are rejected.
_MOBILE = re.compile(r"(6[0-9]|71)[0-9]{6}")

MSG_EMPTY = "Telefon belgiňizi giriziň."
MSG_NOT_DIGITS = "Belgide diňe sanlar bolmaly, mysal üçin: +993 61 234567."
MSG_FOREIGN = "Diňe Türkmenistanyň (+993) ykjam belgileri kabul edilýär."
MSG_LENGTH = "Belgi 8 sanly bolmaly (+993 goşulmazdan), mysal üçin: +993 61 234567."
MSG_NOT_MOBILE = (
    "Bu Türkmenistanyň ykjam belgisine meňzemeýär. Belgi 6 ýa-da 71 bilen başlanmaly, "
    "mysal üçin: +993 61 234567."
)


class InvalidPhone(ValueError):
    """Raised with a message a reader can act on, in the interface language."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def normalize_phone(raw: str) -> str:
    """Turn anything a Turkmen reader might type into `+993XXXXXXXX`, or raise InvalidPhone.

    Accepted shapes, with any spaces, dashes, brackets or dots:
    `+993 6X XXXXXX`, `00993 6X XXXXXX`, `993 6X XXXXXX`, `8 6X XXXXXX`, `6X XXXXXX`.
    """
    compact = _SEPARATORS.sub("", raw or "")
    if not compact:
        raise InvalidPhone(MSG_EMPTY)

    has_plus = compact.startswith("+")
    digits = compact[1:] if has_plus else compact
    if not _DIGITS.fullmatch(digits):
        raise InvalidPhone(MSG_NOT_DIGITS)

    if has_plus:
        # An explicit international prefix must be Turkmenistan's.
        if not digits.startswith("993"):
            raise InvalidPhone(MSG_FOREIGN)
        national = digits[3:]
    elif digits.startswith("00"):
        if not digits.startswith("00993"):
            raise InvalidPhone(MSG_FOREIGN)
        national = digits[5:]
    elif len(digits) == 11 and digits.startswith("993"):
        national = digits[3:]
    elif len(digits) == 9 and digits.startswith("8"):
        # Domestic trunk prefix: 8 6X XXXXXX.
        national = digits[1:]
    else:
        national = digits

    if len(national) != 8:
        raise InvalidPhone(MSG_LENGTH)
    if not _MOBILE.fullmatch(national):
        raise InvalidPhone(MSG_NOT_MOBILE)
    return "+993" + national


def format_phone(canonical: str) -> str:
    """`+99361234567` -> `+993 61 234567`, for display only. Never stored."""
    return f"{canonical[:4]} {canonical[4:6]} {canonical[6:]}"
