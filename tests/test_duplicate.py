"""Tests for possible-duplicate-charge detection (ADR 0002).

All merchants and amounts here are made up. Dates are offsets in days from a fixed
start, so gaps are exact and easy to check against the ADR 0002 windows.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from second_look.duplicate import detect_duplicates
from second_look.models import RecurringFlag, Transaction

START = date(2024, 1, 1)


def d(offset: int) -> date:
    return START + timedelta(days=offset)


def txn(line: int, offset: int, amount: str, description: str = "COFFEE SHOP") -> Transaction:
    return Transaction(line=line, date=d(offset), description=description, amount=Decimal(amount))


def test_flags_two_close_charges_of_the_same_amount() -> None:
    charges = [txn(2, 0, "4.50"), txn(3, 1, "4.50")]
    flags = detect_duplicates(charges, recurring_flags=[])
    assert len(flags) == 1
    flag = flags[0]
    assert flag.type == "duplicate"
    assert flag.lines == (2, 3)
    assert flag.merchant == "COFFEE SHOP"
    assert flag.amount == Decimal("4.50")
    assert flag.first_date == d(0)
    assert flag.second_date == d(1)
    assert "Two charges of $4.50 at COFFEE SHOP" in flag.reason
    assert "2024-01-01 and 2024-01-02" in flag.reason
    assert "within 2 days" in flag.reason


def test_does_not_flag_charges_outside_the_window() -> None:
    charges = [txn(2, 0, "4.50"), txn(3, 3, "4.50")]  # 3 days apart, the window is 2
    assert detect_duplicates(charges, recurring_flags=[]) == []


def test_does_not_flag_charges_right_at_the_window_edge() -> None:
    charges = [txn(2, 0, "4.50"), txn(3, 2, "4.50")]  # exactly 2 days, inside the window
    assert len(detect_duplicates(charges, recurring_flags=[])) == 1


def test_does_not_flag_different_amounts() -> None:
    charges = [txn(2, 0, "4.50"), txn(3, 1, "9.00")]
    assert detect_duplicates(charges, recurring_flags=[]) == []


def test_does_not_flag_different_merchants() -> None:
    charges = [txn(2, 0, "4.50", "COFFEE SHOP"), txn(3, 1, "4.50", "GROCERY STORE")]
    assert detect_duplicates(charges, recurring_flags=[]) == []


def test_ignores_money_coming_in() -> None:
    charges = [
        txn(2, 0, "4.50"),
        Transaction(line=3, date=d(1), description="COFFEE SHOP", amount=Decimal("-4.50")),
    ]
    assert detect_duplicates(charges, recurring_flags=[]) == []


def test_a_refund_within_the_lookahead_clears_the_pair() -> None:
    charges = [
        txn(2, 0, "4.50"),
        txn(3, 1, "4.50"),
        Transaction(line=4, date=d(10), description="COFFEE SHOP", amount=Decimal("-4.50")),
    ]
    assert detect_duplicates(charges, recurring_flags=[]) == []


def test_a_refund_after_the_lookahead_does_not_clear_the_pair() -> None:
    charges = [
        txn(2, 0, "4.50"),
        txn(3, 1, "4.50"),
        Transaction(line=4, date=d(20), description="COFFEE SHOP", amount=Decimal("-4.50")),
    ]
    assert len(detect_duplicates(charges, recurring_flags=[])) == 1


def test_a_refund_of_a_different_amount_does_not_clear_the_pair() -> None:
    charges = [
        txn(2, 0, "4.50"),
        txn(3, 1, "4.50"),
        Transaction(line=4, date=d(5), description="COFFEE SHOP", amount=Decimal("-9.00")),
    ]
    assert len(detect_duplicates(charges, recurring_flags=[])) == 1


def test_a_habit_of_close_pairs_is_not_flagged() -> None:
    # A transit fare charged twice a day, four days running: three or more close
    # pairs at the same merchant and amount looks like a habit, not a mistake.
    charges = [
        txn(2, 0, "3.25"),
        txn(3, 0, "3.25"),
        txn(4, 1, "3.25"),
        txn(5, 1, "3.25"),
        txn(6, 2, "3.25"),
        txn(7, 2, "3.25"),
    ]
    assert detect_duplicates(charges, recurring_flags=[]) == []


def test_two_close_pairs_are_still_flagged() -> None:
    # Below the habit count of three pairs, so both pairs are flagged.
    charges = [
        txn(2, 0, "3.25"),
        txn(3, 0, "3.25"),
        txn(4, 10, "3.25"),
        txn(5, 10, "3.25"),
    ]
    flags = detect_duplicates(charges, recurring_flags=[])
    assert len(flags) == 2


def test_a_charge_already_counted_as_recurring_is_excluded() -> None:
    charges = [txn(2, 0, "4.50"), txn(3, 1, "4.50")]
    recurring = RecurringFlag(
        type="recurring",
        lines=(2, 3),
        merchant="COFFEE SHOP",
        period="weekly",
        active=True,
        amount=Decimal("4.50"),
        count=2,
        first_date=d(0),
        last_date=d(1),
        yearly_cost=Decimal("234.00"),
        reason="made up for this test",
    )
    assert detect_duplicates(charges, recurring_flags=[recurring]) == []


def test_a_charge_partly_recurring_only_excludes_that_line() -> None:
    # Only line 2 is recurring; line 3 is still free to pair with line 4.
    charges = [txn(2, 0, "4.50"), txn(3, 1, "4.50"), txn(4, 2, "4.50")]
    recurring = RecurringFlag(
        type="recurring",
        lines=(2,),
        merchant="COFFEE SHOP",
        period="weekly",
        active=True,
        amount=Decimal("4.50"),
        count=1,
        first_date=d(0),
        last_date=d(0),
        yearly_cost=None,
        reason="made up for this test",
    )
    flags = detect_duplicates(charges, recurring_flags=[recurring])
    assert len(flags) == 1
    assert flags[0].lines == (3, 4)
