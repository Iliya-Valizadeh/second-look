"""Charges that stand out against the user's own history (ADR 0002).

`detect_unusual` runs two comparisons and two simple rules on charges that are not
part of a recognized recurring series, since a recurring charge's price change is
already covered by the price increase rule. It says nothing until the statement holds
at least `MIN_STATEMENT_DAYS` days and `MIN_STATEMENT_CHARGES` charges: "unusual for
you" needs a record of what is usual.

The modified z-score (Iglewicz and Hoaglin, cited in ADR 0002) scores a charge's log
amount against its own merchant's history and its own category's history. Two simple
rules, a new merchant and a very large charge, catch the cases with too little
history for a score. When more than one test fires on a charge, they share one flag,
so the sentences are joined into its one `reason`.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Sequence
from datetime import date as Date
from decimal import Decimal

from .merchant import merchant_key
from .models import RecurringFlag, Transaction, UnusualFlag
from .thresholds import (
    LARGE_CHARGE_RATIO,
    MIN_CATEGORY_HISTORY,
    MIN_LOG_SCALE,
    MIN_MERCHANT_HISTORY,
    MIN_STATEMENT_CHARGES,
    MIN_STATEMENT_DAYS,
    NEW_MERCHANT_MIN_DAYS,
    NEW_MERCHANT_RATIO,
    UNUSUAL_MIN_AMOUNT,
    UNUSUAL_MIN_RATIO,
    Z_THRESHOLD,
)

_MAD_TO_STD = 1.4826


def detect_unusual(
    transactions: Sequence[Transaction], recurring_flags: Sequence[RecurringFlag]
) -> list[UnusualFlag]:
    """Find charges that stand out against the user's own history in `transactions`.

    `recurring_flags` are the series `detect_recurring` already found for this same
    statement. Their charges are excluded, since a price change on them is covered by
    the price increase rule instead.
    """
    charges = [t for t in transactions if t.amount > 0]
    if len(charges) < MIN_STATEMENT_CHARGES:
        return []
    statement_start = min(t.date for t in charges)
    statement_end = max(t.date for t in charges)
    if (statement_end - statement_start).days < MIN_STATEMENT_DAYS:
        return []

    recurring_lines = {line for flag in recurring_flags for line in flag.lines}
    eligible = [t for t in charges if t.line not in recurring_lines]
    all_median = statistics.median(t.amount for t in charges)

    by_merchant: dict[str, list[Transaction]] = {}
    by_category: dict[str, list[Transaction]] = {}
    first_seen_line: dict[str, int] = {}
    for txn in sorted(eligible, key=lambda t: (t.date, t.line)):
        key = merchant_key(txn.description)
        by_merchant.setdefault(key, []).append(txn)
        first_seen_line.setdefault(key, txn.line)
        if txn.category is not None:
            by_category.setdefault(txn.category, []).append(txn)

    flags: list[UnusualFlag] = []
    for txn in eligible:
        key = merchant_key(txn.description)
        reasons: list[str] = []

        merchant_history = [t for t in by_merchant[key] if t.line != txn.line]
        merchant_reason = _merchant_reason(txn, merchant_history)
        if merchant_reason is not None:
            reasons.append(merchant_reason)

        if txn.category is not None:
            category_history = [t for t in by_category[txn.category] if t.line != txn.line]
            category_reason = _category_reason(txn, category_history)
            if category_reason is not None:
                reasons.append(category_reason)

        if first_seen_line[key] == txn.line:
            new_merchant_reason = _new_merchant_reason(txn, statement_start, all_median)
            if new_merchant_reason is not None:
                reasons.append(new_merchant_reason)

        large_reason = _large_charge_reason(txn, all_median)
        if large_reason is not None:
            reasons.append(large_reason)

        if reasons:
            flags.append(
                UnusualFlag(
                    type="unusual",
                    lines=(txn.line,),
                    merchant=txn.description,
                    date=txn.date,
                    amount=txn.amount,
                    reason=" ".join(reasons),
                )
            )
    return flags


def _modified_z(amount: Decimal, history: Sequence[Transaction]) -> float:
    logs = [math.log(float(t.amount)) for t in history]
    median_log = statistics.median(logs)
    mad = statistics.median(abs(value - median_log) for value in logs)
    scale = max(_MAD_TO_STD * mad, MIN_LOG_SCALE)
    return (math.log(float(amount)) - median_log) / scale


def _passes_score(
    txn: Transaction, history: Sequence[Transaction], min_history: int
) -> Decimal | None:
    """Return the history's median amount when the score and the ratio rules both fire."""
    if len(history) < min_history:
        return None
    if _modified_z(txn.amount, history) <= Z_THRESHOLD:
        return None
    median_amount = statistics.median(t.amount for t in history)
    if txn.amount < median_amount * UNUSUAL_MIN_RATIO or txn.amount < UNUSUAL_MIN_AMOUNT:
        return None
    return median_amount


def _merchant_reason(txn: Transaction, history: Sequence[Transaction]) -> str | None:
    median_amount = _passes_score(txn, history, MIN_MERCHANT_HISTORY)
    if median_amount is None:
        return None
    ratio = txn.amount / median_amount
    return (
        f"{_fmt_money(txn.amount)} at {txn.description} on {txn.date.isoformat()} is "
        f"{_fmt_ratio(ratio)} times your usual amount there "
        f"(usual: {_fmt_money(median_amount)}, from {len(history)} other charges)."
    )


def _category_reason(txn: Transaction, history: Sequence[Transaction]) -> str | None:
    median_amount = _passes_score(txn, history, MIN_CATEGORY_HISTORY)
    if median_amount is None:
        return None
    ratio = txn.amount / median_amount
    return (
        f"{_fmt_money(txn.amount)} at {txn.description} on {txn.date.isoformat()} is "
        f"{_fmt_ratio(ratio)} times your usual amount for {txn.category} "
        f"(usual: {_fmt_money(median_amount)}, from {len(history)} other charges)."
    )


def _new_merchant_reason(
    txn: Transaction, statement_start: Date, all_median: Decimal
) -> str | None:
    days = (txn.date - statement_start).days
    if days < NEW_MERCHANT_MIN_DAYS:
        return None
    if txn.amount < all_median * NEW_MERCHANT_RATIO or txn.amount < UNUSUAL_MIN_AMOUNT:
        return None
    ratio = txn.amount / all_median
    return (
        f"{_fmt_money(txn.amount)} on {txn.date.isoformat()} is your first charge at "
        f"{txn.description} in {days} days of history, and {_fmt_ratio(ratio)} times "
        f"your typical charge ({_fmt_money(all_median)})."
    )


def _large_charge_reason(txn: Transaction, all_median: Decimal) -> str | None:
    if txn.amount < all_median * LARGE_CHARGE_RATIO or txn.amount < UNUSUAL_MIN_AMOUNT:
        return None
    ratio = txn.amount / all_median
    return (
        f"{_fmt_money(txn.amount)} at {txn.description} on {txn.date.isoformat()} is "
        f"{_fmt_ratio(ratio)} times your typical charge ({_fmt_money(all_median)})."
    )


def _fmt_money(amount: Decimal) -> str:
    return f"${amount:.2f}"


def _fmt_ratio(ratio: Decimal) -> str:
    return f"{ratio:.1f}"
