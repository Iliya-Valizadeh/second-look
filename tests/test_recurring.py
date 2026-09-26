"""Tests for recurring-charge and price-increase detection (ADR 0002).

All merchants and amounts here are made up. Dates are offsets in days from a fixed
start, so gaps are exact and easy to check against the ADR 0002 windows.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from second_look.models import Transaction
from second_look.recurring import (
    _group_by_amount,
    _is_close_amount,
    detect_period,
    detect_recurring,
)

START = date(2024, 1, 1)


def d(offset: int) -> date:
    return START + timedelta(days=offset)


def txn(line: int, offset: int, amount: str, description: str = "ACME SUB") -> Transaction:
    return Transaction(line=line, date=d(offset), description=description, amount=Decimal(amount))


# --- close-amount tolerance ---------------------------------------------------------


def test_close_amount_uses_the_five_cent_floor_on_small_amounts() -> None:
    # 3% of $1.00 is 3 cents, below the 5 cent floor, so the floor applies.
    assert _is_close_amount(Decimal("1.00"), Decimal("1.05"))
    assert not _is_close_amount(Decimal("1.00"), Decimal("1.06"))


def test_close_amount_uses_three_percent_on_larger_amounts() -> None:
    assert _is_close_amount(Decimal("100.00"), Decimal("103.00"))
    assert not _is_close_amount(Decimal("100.00"), Decimal("103.01"))


def test_group_by_amount_joins_the_closest_group_when_several_fit() -> None:
    charges = [txn(2, 0, "10.00"), txn(3, 10, "20.00"), txn(4, 20, "10.02")]
    groups = _group_by_amount(charges)
    assert [t.line for t in groups[0]] == [2, 4]
    assert [t.line for t in groups[1]] == [3]


# --- detect_period -------------------------------------------------------------------


def test_detect_period_finds_weekly() -> None:
    dates = [d(0), d(7), d(14), d(21)]
    rule = detect_period(dates)
    assert rule is not None and rule.name == "weekly"


def test_detect_period_finds_monthly() -> None:
    dates = [d(0), d(30), d(61)]
    rule = detect_period(dates)
    assert rule is not None and rule.name == "monthly"


def test_detect_period_finds_yearly() -> None:
    dates = [d(0), d(365)]
    rule = detect_period(dates)
    assert rule is not None and rule.name == "yearly"


def test_detect_period_needs_the_minimum_count() -> None:
    assert detect_period([d(0), d(30)]) is None  # monthly needs three


def test_detect_period_rejects_gaps_outside_every_window() -> None:
    assert detect_period([d(0), d(10), d(20)]) is None


def test_detect_period_allows_one_skipped_charge_for_monthly() -> None:
    dates = [d(0), d(30), d(90), d(120)]  # one ~60-day gap, a skipped month
    rule = detect_period(dates)
    assert rule is not None and rule.name == "monthly"


def test_detect_period_does_not_allow_a_skip_for_yearly() -> None:
    dates = [d(0), d(365), d(1095)]  # a skipped year is outside the yearly window
    assert detect_period(dates) is None


def test_detect_period_needs_a_second_charge() -> None:
    assert detect_period([d(0)]) is None


# --- detect_recurring: basic series ---------------------------------------------------


def test_flags_an_active_monthly_subscription() -> None:
    charges = [txn(2, 0, "9.99"), txn(3, 30, "9.99"), txn(4, 60, "9.99")]
    recurring, price = detect_recurring(charges, statement_end=d(65))
    assert price == []
    assert len(recurring) == 1
    flag = recurring[0]
    assert flag.type == "recurring"
    assert flag.period == "monthly"
    assert flag.active is True
    assert flag.count == 3
    assert flag.lines == (2, 3, 4)
    assert flag.yearly_cost == Decimal("119.88")
    assert "every month" in flag.reason
    assert "3 times" in flag.reason


def test_marks_a_series_stopped_when_its_last_charge_is_too_old() -> None:
    charges = [txn(2, 0, "9.99"), txn(3, 30, "9.99"), txn(4, 60, "9.99")]
    recurring, _ = detect_recurring(charges, statement_end=d(200))
    flag = recurring[0]
    assert flag.active is False
    assert flag.yearly_cost is None
    assert "seems to have stopped" in flag.reason


def test_uses_the_twice_a_year_wording_for_a_two_charge_yearly_series() -> None:
    charges = [txn(2, 0, "59.99"), txn(3, 365, "59.99")]
    recurring, _ = detect_recurring(charges, statement_end=d(370))
    assert len(recurring) == 1
    flag = recurring[0]
    assert flag.period == "yearly"
    assert "twice, a year apart" in flag.reason
    assert flag.yearly_cost == Decimal("59.99")


def test_ignores_a_series_with_too_few_charges() -> None:
    charges = [txn(2, 0, "9.99"), txn(3, 30, "9.99")]  # monthly needs three
    recurring, price = detect_recurring(charges, statement_end=d(35))
    assert recurring == [] and price == []


def test_ignores_money_coming_in() -> None:
    charges = [
        txn(2, 0, "9.99"),
        txn(3, 30, "9.99"),
        txn(4, 60, "9.99"),
        Transaction(line=5, date=d(10), description="ACME SUB", amount=Decimal("-9.99")),
    ]
    recurring, _ = detect_recurring(charges, statement_end=d(65))
    assert len(recurring) == 1 and recurring[0].count == 3


def test_keeps_different_merchants_separate() -> None:
    charges = [
        txn(2, 0, "9.99", "SUB A"),
        txn(3, 30, "9.99", "SUB A"),
        txn(4, 60, "9.99", "SUB A"),
        txn(5, 0, "4.99", "SUB B"),
        txn(6, 30, "4.99", "SUB B"),
        txn(7, 60, "4.99", "SUB B"),
    ]
    recurring, _ = detect_recurring(charges, statement_end=d(65))
    assert {flag.merchant for flag in recurring} == {"SUB A", "SUB B"}


# --- detect_recurring: price increases ------------------------------------------------


def test_merges_a_price_increase_into_one_recurring_flag() -> None:
    charges = [
        txn(2, 0, "9.99"),
        txn(3, 30, "9.99"),
        txn(4, 60, "9.99"),
        txn(5, 90, "11.99"),
        txn(6, 120, "11.99"),
    ]
    recurring, price = detect_recurring(charges, statement_end=d(125))

    assert len(recurring) == 1
    flag = recurring[0]
    assert flag.count == 5
    assert flag.lines == (2, 3, 4, 5, 6)
    assert flag.amount == Decimal("11.99")
    assert flag.active is True

    assert len(price) == 1
    price_flag = price[0]
    assert price_flag.type == "price_increase"
    assert price_flag.lines == (5, 6)
    assert price_flag.old_amount == Decimal("9.99")
    assert price_flag.new_amount == Decimal("11.99")
    assert price_flag.period == "monthly"
    assert "20% more" in price_flag.reason
    assert "$24.00 a year" in price_flag.reason


def test_a_price_drop_is_not_flagged() -> None:
    charges = [
        txn(2, 0, "9.99"),
        txn(3, 30, "9.99"),
        txn(4, 60, "9.99"),
        txn(5, 90, "7.99"),
        txn(6, 120, "7.99"),
    ]
    recurring, price = detect_recurring(charges, statement_end=d(125))
    assert price == []
    assert len(recurring) == 1 and recurring[0].count == 3


def test_one_charge_at_a_new_monthly_price_is_not_enough() -> None:
    charges = [
        txn(2, 0, "9.99"),
        txn(3, 30, "9.99"),
        txn(4, 60, "9.99"),
        txn(5, 90, "11.99"),
    ]
    recurring, price = detect_recurring(charges, statement_end=d(95))
    assert price == []
    assert len(recurring) == 1 and recurring[0].count == 3


def test_one_charge_at_a_new_yearly_price_is_enough() -> None:
    charges = [txn(2, 0, "59.99"), txn(3, 365, "59.99"), txn(4, 730, "69.99")]
    recurring, price = detect_recurring(charges, statement_end=d(735))
    assert len(price) == 1
    assert price[0].old_amount == Decimal("59.99")
    assert price[0].new_amount == Decimal("69.99")
    assert len(recurring) == 1 and recurring[0].count == 3


def test_a_price_increase_must_keep_the_same_spacing() -> None:
    charges = [
        txn(2, 0, "9.99"),
        txn(3, 30, "9.99"),
        txn(4, 60, "9.99"),
        txn(5, 65, "11.99"),  # far too soon to be the next monthly charge
        txn(6, 95, "11.99"),
    ]
    recurring, price = detect_recurring(charges, statement_end=d(100))
    assert price == []
    assert len(recurring) == 1 and recurring[0].count == 3
