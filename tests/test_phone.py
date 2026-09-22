"""Phone normalisation — the one place in the test suite that is meant to be exhaustive."""
from __future__ import annotations

import pytest

from app.phone import (
    MSG_EMPTY,
    MSG_FOREIGN,
    MSG_LENGTH,
    MSG_NOT_DIGITS,
    MSG_NOT_MOBILE,
    InvalidPhone,
    format_phone,
    normalize_phone,
)

CANONICAL = "+99361234567"

SAME_NUMBER_TYPED_EVERY_WAY = [
    # International, with and without grouping
    "+99361234567",
    "+993 61 234567",
    "+993 61 23 45 67",
    "+993 (61) 23-45-67",
    "+993-61-234-567",
    "+ 993 61 234567",
    "+993.61.23.45.67",
    "+99 361234567",  # grouping is ignored entirely; only the digits count
    # International without the plus
    "99361234567",
    "993 61 234567",
    "0099361234567",
    "00 993 61 234567",
    # Domestic trunk prefix 8
    "861234567",
    "8 61 234567",
    "8 (61) 23-45-67",
    "8-61-234567",
    # Bare national number
    "61234567",
    "61 234567",
    "61 23 45 67",
    "(61) 23-45-67",
    # Surrounding and odd whitespace
    "  +993 61 234567  ",
    "\t61234567\n",
    "+993 61 234567",  # non-breaking spaces, as pasted from a contact card
]


@pytest.mark.parametrize("raw", SAME_NUMBER_TYPED_EVERY_WAY)
def test_every_accepted_format_maps_to_one_stored_string(raw):
    assert normalize_phone(raw) == CANONICAL


def test_all_formats_agree_with_each_other():
    assert {normalize_phone(raw) for raw in SAME_NUMBER_TYPED_EVERY_WAY} == {CANONICAL}


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("+993 62 000000", "+99362000000"),
        ("8 63 999999", "+99363999999"),
        ("64 123456", "+99364123456"),
        ("65123456", "+99365123456"),
        ("+993 66 123456", "+99366123456"),
        ("867123456", "+99367123456"),
        ("68 123456", "+99368123456"),
        ("+993 71 234567", "+99371234567"),
        ("8 71 23 45 67", "+99371234567"),
        ("71234567", "+99371234567"),
    ],
)
def test_other_mobile_prefixes_are_accepted(raw, expected):
    assert normalize_phone(raw) == expected


def test_normalising_is_idempotent():
    assert normalize_phone(normalize_phone("8 61 234567")) == CANONICAL


@pytest.mark.parametrize(
    "raw, message",
    [
        # Empty
        ("", MSG_EMPTY),
        ("   ", MSG_EMPTY),
        ("-()", MSG_EMPTY),
        (None, MSG_EMPTY),
        # Not digits
        ("abc", MSG_NOT_DIGITS),
        ("+993 61 23456a", MSG_NOT_DIGITS),
        ("61234567 ext 2", MSG_NOT_DIGITS),
        ("++99361234567", MSG_NOT_DIGITS),
        ("61234567+", MSG_NOT_DIGITS),
        ("+993/61/234567", MSG_NOT_DIGITS),
        ("٦١٢٣٤٥٦٧", MSG_NOT_DIGITS),  # Arabic-Indic digits
        ("６１２３４５６７", MSG_NOT_DIGITS),  # full-width digits
        # Foreign country codes
        ("+7 912 345 67 89", MSG_FOREIGN),
        ("+90 532 123 45 67", MSG_FOREIGN),
        ("007 912 3456789", MSG_FOREIGN),
        ("+", MSG_NOT_DIGITS),
        # Wrong length
        ("6123456", MSG_LENGTH),
        ("612345678", MSG_LENGTH),
        ("+993 61 23456", MSG_LENGTH),
        ("+993 61 2345678", MSG_LENGTH),
        ("+993", MSG_LENGTH),
        ("00993", MSG_LENGTH),
        ("8 61 2345678", MSG_LENGTH),
        ("99361234567 1", MSG_LENGTH),
        # Plausible length, not a mobile number
        ("12345678", MSG_NOT_MOBILE),  # Ashgabat landline
        ("+993 12 345678", MSG_NOT_MOBILE),
        ("8 12 345678", MSG_NOT_MOBILE),
        ("+993 72 123456", MSG_NOT_MOBILE),
        ("+993 70 123456", MSG_NOT_MOBILE),
        ("+993 00000000", MSG_NOT_MOBILE),
        ("81234567", MSG_NOT_MOBILE),  # 8 digits starting with 8 is not trunk-prefixed
    ],
)
def test_implausible_numbers_are_rejected_with_a_readable_message(raw, message):
    with pytest.raises(InvalidPhone) as excinfo:
        normalize_phone(raw)
    assert excinfo.value.message == message


def test_format_phone_groups_for_display():
    assert format_phone(CANONICAL) == "+993 61 234567"
