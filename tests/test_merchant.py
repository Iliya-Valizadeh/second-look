"""Tests for merchant-name cleaning (ADR 0002). Fixtures are made-up, not real merchants."""

from __future__ import annotations

import pytest

from second_look.merchant import merchant_key


@pytest.mark.parametrize(
    ("description", "expected"),
    [
        ("SQ *JOE'S COFFEE TORONTO ON", "JOE'S COFFEE TORONTO"),
        ("TST*MAPLE DINER MONTREAL QC", "MAPLE DINER MONTREAL"),
        ("PAYPAL *SUBSCRIPTIONCO", "SUBSCRIPTIONCO"),
        ("PP*SMALLSELLER", "SMALLSELLER"),
    ],
)
def test_processor_prefixes_are_removed(description: str, expected: str) -> None:
    assert merchant_key(description) == expected


def test_store_numbers_are_removed() -> None:
    assert merchant_key("LOBLAWS #482 TORONTO ON") == "LOBLAWS TORONTO"


def test_long_reference_numbers_are_removed_but_short_ones_stay() -> None:
    assert merchant_key("SOMESHOP REF 12345678") == "SOMESHOP REF"
    assert merchant_key("SOMESHOP UNIT 12") == "SOMESHOP UNIT 12"


def test_punctuation_is_replaced_except_ampersand_and_apostrophe() -> None:
    assert merchant_key("A&W RESTAURANT") == "A&W RESTAURANT"
    assert merchant_key("TIM'S COFFEE.") == "TIM'S COFFEE"


def test_a_trailing_province_code_is_removed() -> None:
    assert merchant_key("CORNER STORE VANCOUVER BC") == "CORNER STORE VANCOUVER"


def test_a_trailing_legal_suffix_is_removed() -> None:
    assert merchant_key("WIDGETCO LTD") == "WIDGETCO"
    assert merchant_key("GADGET SUPPLY INC") == "GADGET SUPPLY"


def test_province_then_legal_suffix_are_both_removed_in_order() -> None:
    assert merchant_key("WIDGETCO INC OTTAWA ON") == "WIDGETCO INC OTTAWA"


def test_a_key_that_cleans_to_nothing_falls_back_to_the_upper_case_description() -> None:
    assert merchant_key("123456789") == "123456789"


def test_unicode_is_normalized_before_cleaning() -> None:
    # Full-width Latin letters (NFKC folds these to plain ASCII before upper-casing).
    assert merchant_key("Ｍｅｒｃｈａｎｔ") == "MERCHANT"


def test_the_key_is_grouping_only_and_case_insensitive() -> None:
    assert merchant_key("acme sub") == merchant_key("ACME SUB")
