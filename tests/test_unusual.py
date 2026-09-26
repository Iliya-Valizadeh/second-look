"""Tests for unusual-transaction detection (ADR 0002).

All merchants, amounts and categories here are made up. Dates are offsets in days
from a fixed start. Filler charges give each scenario enough history to pass the
statement-wide gate (`MIN_STATEMENT_DAYS`, `MIN_STATEMENT_CHARGES`) and the per-test
minimum history, while staying too even in amount to trigger anything themselves.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from second_look.models import RecurringFlag, Transaction
from second_look.unusual import detect_unusual

START = date(2024, 1, 1)


def d(offset: int) -> date:
    return START + timedelta(days=offset)


def txn(
    line: int,
    offset: int,
    amount: str,
    description: str = "FILLER STORE",
    category: str | None = None,
) -> Transaction:
    return Transaction(
        line=line,
        date=d(offset),
        description=description,
        amount=Decimal(amount),
        category=category,
    )


def _filler(start_line: int, count: int, step: int = 3, amount: str = "10.00") -> list[Transaction]:
    return [txn(start_line + i, i * step, amount) for i in range(count)]


# --- the statement-wide gate ---------------------------------------------------------


def test_no_flags_below_the_minimum_charge_count() -> None:
    charges = _filler(2, 20) + [txn(22, 100, "500.00", "BIG ONE TIME PURCHASE")]
    assert detect_unusual(charges, recurring_flags=[]) == []


def test_no_flags_below_the_minimum_statement_length() -> None:
    charges = _filler(2, 30, step=1) + [txn(32, 20, "500.00", "BIG ONE TIME PURCHASE")]
    # 30 filler charges a day apart span 29 days, under the 60-day minimum.
    assert detect_unusual(charges, recurring_flags=[]) == []


# --- per-merchant modified z-score ---------------------------------------------------


def test_flags_a_large_charge_against_its_own_merchant_history() -> None:
    charges = _filler(2, 29) + [txn(31, 10, "40.00")]  # same merchant as the filler
    flags = detect_unusual(charges, recurring_flags=[])
    assert len(flags) == 1
    flag = flags[0]
    assert flag.type == "unusual"
    assert flag.lines == (31,)
    assert flag.merchant == "FILLER STORE"
    assert flag.amount == Decimal("40.00")
    assert flag.reason == (
        "$40.00 at FILLER STORE on 2024-01-11 is 4.0 times your usual amount there "
        "(usual: $10.00, from 29 other charges)."
    )


def test_a_high_score_with_too_small_a_ratio_is_not_flagged() -> None:
    # The score fires (a $15 charge against a very tight $10 history), but the ratio
    # rule (at least twice the usual amount) does not, so nothing is flagged.
    charges = _filler(2, 29) + [txn(31, 10, "15.00")]
    assert detect_unusual(charges, recurring_flags=[]) == []


def test_does_not_flag_a_merchant_with_too_little_history() -> None:
    charges = _filler(2, 29) + [
        txn(31, 10, "40.00", "NEW SPOT"),  # only one charge at this merchant
    ]
    assert detect_unusual(charges, recurring_flags=[]) == []


# --- per-category modified z-score ---------------------------------------------------


def test_flags_a_large_charge_against_its_own_category_history() -> None:
    groc_a = [txn(2 + i, i * 5, "8.00", "GROC A", category="GROCERY") for i in range(15)]
    groc_b = [txn(17 + i, i * 5, "8.00", "GROC B", category="GROCERY") for i in range(15)]
    outlier = txn(32, 20, "60.00", "GROC C", category="GROCERY")
    flags = detect_unusual([*groc_a, *groc_b, outlier], recurring_flags=[])
    assert len(flags) == 1
    flag = flags[0]
    assert flag.lines == (32,)
    assert flag.merchant == "GROC C"
    assert flag.reason == (
        "$60.00 at GROC C on 2024-01-21 is 7.5 times your usual amount for GROCERY "
        "(usual: $8.00, from 30 other charges)."
    )


def test_does_not_score_by_category_when_there_is_no_category() -> None:
    groc_a = [txn(2 + i, i * 5, "8.00", "GROC A") for i in range(15)]
    groc_b = [txn(17 + i, i * 5, "8.00", "GROC B") for i in range(15)]
    outlier = txn(32, 20, "60.00", "GROC C")  # no category on any row this time
    assert detect_unusual([*groc_a, *groc_b, outlier], recurring_flags=[]) == []


# --- new merchant, large amount -------------------------------------------------------


def test_flags_a_first_charge_at_a_new_merchant() -> None:
    charges = _filler(2, 30) + [txn(32, 65, "45.00", "NEW GADGET STORE")]
    flags = detect_unusual(charges, recurring_flags=[])
    assert len(flags) == 1
    flag = flags[0]
    assert flag.merchant == "NEW GADGET STORE"
    assert flag.reason == (
        "$45.00 on 2024-03-06 is your first charge at NEW GADGET STORE in 65 days of "
        "history, and 4.5 times your typical charge ($10.00)."
    )


def test_does_not_flag_a_new_merchant_whose_amount_is_too_small() -> None:
    # Far enough into the statement, but the amount is not 3 times the median, so
    # the new-merchant rule does not fire.
    charges = _filler(2, 30) + [txn(32, 65, "15.00", "NEW GADGET STORE")]
    assert detect_unusual(charges, recurring_flags=[]) == []


def test_does_not_flag_a_new_merchant_too_early_in_the_statement() -> None:
    charges = _filler(2, 30) + [txn(32, 10, "45.00", "NEW GADGET STORE")]  # only 10 days in
    assert detect_unusual(charges, recurring_flags=[]) == []


# --- very large charge ---------------------------------------------------------------


def test_flags_a_very_large_charge_at_an_established_merchant() -> None:
    charges = (
        _filler(2, 28)
        + [txn(30, 5, "10.00", "LARGE MART"), txn(31, 40, "10.00", "LARGE MART")]
        + [txn(32, 70, "150.00", "LARGE MART")]
    )
    flags = detect_unusual(charges, recurring_flags=[])
    assert len(flags) == 1
    flag = flags[0]
    assert flag.merchant == "LARGE MART"
    assert flag.reason == (
        "$150.00 at LARGE MART on 2024-03-11 is 15.0 times your typical charge ($10.00)."
    )


def test_many_repeated_small_charges_do_not_make_ordinary_charges_look_large() -> None:
    # ADR 0006: 150 transit fares of $3.35 would make the plain median $3.35, so every
    # grocery bill of $34 or more would look "10 times your typical charge". Counting
    # each distinct amount once keeps the typical charge near the grocery bills.
    fares = [txn(2 + i, (i * 2) // 3, "3.35", "CITY TRANSIT") for i in range(150)]
    groceries = [txn(200 + i, i * 4, f"{40 + i * 2}.00", "CORNER GROCER") for i in range(25)]
    assert detect_unusual([*fares, *groceries], recurring_flags=[]) == []


def test_the_typical_charge_leaves_out_the_charge_being_judged() -> None:
    # Every other charge is $10.00. If the $150.00 counted towards its own typical
    # charge, the distinct amounts {10, 150} would give a typical charge of $80.00.
    charges = _filler(2, 30) + [txn(32, 70, "150.00", "ONE OFF STORE")]
    flags = detect_unusual(charges, recurring_flags=[])
    assert len(flags) == 1
    assert "15.0 times your typical charge ($10.00)" in flags[0].reason


# --- recurring exclusion --------------------------------------------------------------


def test_a_charge_already_counted_as_recurring_is_excluded() -> None:
    charges = _filler(2, 28) + [
        txn(30, 5, "10.00", "LARGE MART"),
        txn(31, 40, "10.00", "LARGE MART"),
        txn(32, 70, "150.00", "LARGE MART"),
    ]
    recurring = RecurringFlag(
        type="recurring",
        lines=(32,),
        merchant="LARGE MART",
        period="yearly",
        active=True,
        amount=Decimal("150.00"),
        count=1,
        first_date=d(70),
        last_date=d(70),
        yearly_cost=Decimal("150.00"),
        reason="made up for this test",
    )
    assert detect_unusual(charges, recurring_flags=[recurring]) == []
