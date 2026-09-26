"""Possible duplicate charges: the same amount, at the same merchant, close in time
(ADR 0002).

`detect_duplicates` looks only at charges that `detect_recurring` has not already
claimed, since a recognized recurring charge is a habit, not a billing mistake. A
close pair is also skipped when a refund fixes it, or when the same merchant and
amount pair up this often elsewhere in the statement, which looks like a habit (such
as a transit fare paid twice a day) rather than a double charge.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date as Date
from datetime import timedelta
from decimal import Decimal

from .merchant import merchant_key
from .models import DuplicateFlag, RecurringFlag, Transaction
from .thresholds import DUPLICATE_HABIT_PAIRS, DUPLICATE_WINDOW_DAYS, REFUND_LOOKAHEAD_DAYS


def detect_duplicates(
    transactions: Sequence[Transaction], recurring_flags: Sequence[RecurringFlag]
) -> list[DuplicateFlag]:
    """Find possible duplicate charges in `transactions`.

    `recurring_flags` are the series `detect_recurring` already found for this same
    statement. Their charges are excluded, since an already-recognized recurring
    charge should not also be reported as a possible duplicate.
    """
    recurring_lines = {line for flag in recurring_flags for line in flag.lines}

    charges_by_merchant: dict[str, list[Transaction]] = {}
    refunds_by_merchant: dict[str, list[Transaction]] = {}
    for txn in transactions:
        key = merchant_key(txn.description)
        if txn.amount > 0:
            if txn.line not in recurring_lines:
                charges_by_merchant.setdefault(key, []).append(txn)
        elif txn.amount < 0:
            refunds_by_merchant.setdefault(key, []).append(txn)

    flags: list[DuplicateFlag] = []
    for key, charges in charges_by_merchant.items():
        refunds = refunds_by_merchant.get(key, ())
        by_amount: dict[Decimal, list[Transaction]] = {}
        for txn in sorted(charges, key=lambda t: (t.date, t.line)):
            by_amount.setdefault(txn.amount, []).append(txn)

        for same_amount in by_amount.values():
            pairs = [
                (earlier, later)
                for earlier, later in zip(same_amount, same_amount[1:], strict=False)
                if (later.date - earlier.date).days <= DUPLICATE_WINDOW_DAYS
            ]
            if len(pairs) >= DUPLICATE_HABIT_PAIRS:
                continue  # a habit, such as a fare paid twice a day, not a mistake
            for earlier, later in pairs:
                if _has_matching_refund(refunds, earlier.amount, later.date):
                    continue
                flags.append(_make_duplicate_flag(earlier, later))
    return flags


def _has_matching_refund(refunds: Sequence[Transaction], amount: Decimal, after: Date) -> bool:
    deadline = after + timedelta(days=REFUND_LOOKAHEAD_DAYS)
    return any(-refund.amount == amount and after <= refund.date <= deadline for refund in refunds)


def _make_duplicate_flag(earlier: Transaction, later: Transaction) -> DuplicateFlag:
    reason = (
        f"Two charges of {_fmt_money(earlier.amount)} at {later.description}, on "
        f"{earlier.date.isoformat()} and {later.date.isoformat()}. The same amount at "
        f"the same place within {DUPLICATE_WINDOW_DAYS} days can be a double charge."
    )
    return DuplicateFlag(
        type="duplicate",
        lines=(earlier.line, later.line),
        merchant=later.description,
        amount=earlier.amount,
        first_date=earlier.date,
        second_date=later.date,
        reason=reason,
    )


def _fmt_money(amount: Decimal) -> str:
    return f"${amount:.2f}"
