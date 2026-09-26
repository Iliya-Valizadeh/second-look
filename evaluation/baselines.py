"""One simple baseline per flag type (docs/eval_plan.md, "Baselines").

Each baseline reuses the engine's own merchant-name cleaning (`second_look.merchant`),
so the comparison isolates the rule logic, not the text cleaning. A baseline flag is a
plain dict with a `lines` tuple, scored by `matching.py` exactly like an engine flag.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from second_look.merchant import merchant_key
from second_look.models import Transaction
from second_look.thresholds import DUPLICATE_WINDOW_DAYS

from .common import is_close_amount

BASELINE_MIN_RECURRING_COUNT = 3
BASELINE_UNUSUAL_Z = 3.0


def baseline_recurring(transactions: Sequence[Transaction]) -> list[dict[str, Any]]:
    """Group by merchant key and exact amount. 3 or more charges is one flag."""
    groups: dict[tuple[str, Decimal], list[Transaction]] = {}
    for t in transactions:
        if t.amount <= 0:
            continue
        groups.setdefault((merchant_key(t.description), t.amount), []).append(t)

    flags = []
    for (mkey, amount), txns in groups.items():
        if len(txns) >= BASELINE_MIN_RECURRING_COUNT:
            lines = tuple(sorted(t.line for t in txns))
            last_date = max(t.date for t in txns)
            flags.append(
                {"lines": lines, "merchant_key": mkey, "amount": amount, "last_date": last_date}
            )
    return flags


def baseline_price_increase(
    transactions: Sequence[Transaction], recurring_groups: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """For each baseline recurring group, flag the first later, clearly higher charge
    at the same merchant key."""
    by_key: dict[str, list[Transaction]] = {}
    for t in transactions:
        if t.amount > 0:
            by_key.setdefault(merchant_key(t.description), []).append(t)

    flags = []
    for group in recurring_groups:
        later = sorted(
            (t for t in by_key.get(group["merchant_key"], ()) if t.date > group["last_date"]),
            key=lambda t: t.date,
        )
        for t in later:
            if t.amount > group["amount"] and not is_close_amount(t.amount, group["amount"]):
                flags.append({"lines": (t.line,), "new_amount": t.amount})
                break
    return flags


def baseline_duplicate(transactions: Sequence[Transaction]) -> list[dict[str, Any]]:
    """Same merchant key, exact same amount, dates no more than 2 days apart. No
    refund or habit exception."""
    by_key: dict[tuple[str, Decimal], list[Transaction]] = {}
    for t in transactions:
        if t.amount > 0:
            by_key.setdefault((merchant_key(t.description), t.amount), []).append(t)

    flags = []
    for txns in by_key.values():
        ordered = sorted(txns, key=lambda t: (t.date, t.line))
        for earlier, later in zip(ordered, ordered[1:], strict=False):
            if (later.date - earlier.date).days <= DUPLICATE_WINDOW_DAYS:
                flags.append({"lines": (earlier.line, later.line)})
    return flags


def baseline_unusual(transactions: Sequence[Transaction]) -> list[dict[str, Any]]:
    """Ordinary z-score (mean and standard deviation) on the raw amounts. Flag every
    charge more than 3 standard deviations above the mean."""
    charges = [t for t in transactions if t.amount > 0]
    if len(charges) < 2:
        return []
    amounts = [float(t.amount) for t in charges]
    mean = statistics.mean(amounts)
    stdev = statistics.stdev(amounts)
    if stdev == 0:
        return []
    flags = []
    for t, a in zip(charges, amounts, strict=True):
        if (a - mean) / stdev > BASELINE_UNUSUAL_Z:
            flags.append({"lines": (t.line,)})
    return flags
