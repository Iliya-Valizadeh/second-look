"""Recurring charges, their yearly cost, and price increases on them (ADR 0002).

`detect_recurring` groups a statement's charges by merchant key, then by close
amount, then checks the spacing of the dates. A price increase joins two amount
groups at one merchant when the new charges start right after the old series ends,
at the same spacing, and hold at their new amount for the number of charges ADR 0002
requires. The merged series is then reported once, at the new price.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from datetime import date as Date
from decimal import ROUND_HALF_UP, Decimal

from .merchant import merchant_key
from .models import PriceIncreaseFlag, RecurringFlag, Transaction
from .thresholds import (
    ACTIVE_MAX_PERIODS,
    PERIOD_RULES,
    SAME_AMOUNT_ABS,
    SAME_AMOUNT_REL,
    PeriodRule,
)

_CENT = Decimal("0.01")

_ACTIVE_PHRASE = {"weekly": "every week", "monthly": "every month", "yearly": "every year"}
_STOPPED_PHRASE = {"weekly": "weekly", "monthly": "monthly", "yearly": "yearly"}


def detect_recurring(
    transactions: Sequence[Transaction], statement_end: Date
) -> tuple[list[RecurringFlag], list[PriceIncreaseFlag]]:
    """Find recurring charges and price increases in `transactions`.

    `statement_end` is the last date in the statement (ADR 0001 treats it as
    "today"), used to decide whether a series is still active.
    """
    by_merchant: dict[str, list[Transaction]] = {}
    for txn in transactions:
        if txn.amount <= 0:
            continue  # money in, not a charge
        by_merchant.setdefault(merchant_key(txn.description), []).append(txn)

    recurring_flags: list[RecurringFlag] = []
    price_flags: list[PriceIncreaseFlag] = []

    for txns in by_merchant.values():
        ordered = sorted(txns, key=lambda t: (t.date, t.line))
        amount_groups = _group_by_amount(ordered)
        rules = [detect_period([t.date for t in group]) for group in amount_groups]

        used = [False] * len(amount_groups)
        for i, rule in enumerate(rules):
            if used[i] or rule is None:
                continue
            used[i] = True
            merged = list(amount_groups[i])

            candidate_idx = i + 1
            if candidate_idx < len(amount_groups) and not used[candidate_idx]:
                candidate = amount_groups[candidate_idx]
                if _is_price_increase(amount_groups[i], candidate, rule):
                    used[candidate_idx] = True
                    old_amount = statistics.median(t.amount for t in amount_groups[i])
                    new_amount = statistics.median(t.amount for t in candidate)
                    price_flags.append(_make_price_flag(candidate, old_amount, new_amount, rule))
                    merged.extend(candidate)

            recurring_flags.append(_make_recurring_flag(merged, rule, statement_end))

    return recurring_flags, price_flags


def detect_period(dates: Sequence[Date]) -> PeriodRule | None:
    """Return the period a sorted list of charge dates fits, or `None`.

    A period fits when there are at least its minimum number of charges and every
    gap between consecutive dates is inside its window (weekly and monthly allow one
    gap of about two periods, for one skipped charge).
    """
    if len(dates) < 2:
        return None
    for rule in PERIOD_RULES:
        if len(dates) >= rule.min_charges and _gaps_match_rule(dates, rule):
            return rule
    return None


def _gaps_match_rule(dates: Sequence[Date], rule: PeriodRule) -> bool:
    used_skip = False
    for earlier, later in zip(dates, dates[1:], strict=False):
        gap = (later - earlier).days
        if rule.gap_low_days <= gap <= rule.gap_high_days:
            continue
        if (
            rule.allow_one_skip
            and not used_skip
            and 2 * rule.gap_low_days <= gap <= 2 * rule.gap_high_days
        ):
            used_skip = True
            continue
        return False
    return True


def _is_close_amount(a: Decimal, b: Decimal) -> bool:
    tolerance = max(SAME_AMOUNT_ABS, min(a, b) * SAME_AMOUNT_REL)
    return abs(a - b) <= tolerance


def _group_by_amount(ordered: list[Transaction]) -> list[list[Transaction]]:
    """Group same-merchant charges, in date order, by close amount (ADR 0002).

    Each charge joins the existing group whose median amount is closest and within
    tolerance, or starts a new group.
    """
    groups: list[list[Transaction]] = []
    medians: list[Decimal] = []
    for txn in ordered:
        best_idx: int | None = None
        best_diff: Decimal | None = None
        for idx, median in enumerate(medians):
            if not _is_close_amount(txn.amount, median):
                continue
            diff = abs(txn.amount - median)
            if best_diff is None or diff < best_diff:
                best_idx, best_diff = idx, diff
        if best_idx is None:
            groups.append([txn])
            medians.append(txn.amount)
        else:
            groups[best_idx].append(txn)
            medians[best_idx] = statistics.median(t.amount for t in groups[best_idx])
    return groups


def _is_price_increase(
    old_group: Sequence[Transaction], candidate: Sequence[Transaction], rule: PeriodRule
) -> bool:
    if len(candidate) < rule.price_rise_min_new:
        return False
    old_amount = statistics.median(t.amount for t in old_group)
    new_amount = statistics.median(t.amount for t in candidate)
    if new_amount <= old_amount or _is_close_amount(old_amount, new_amount):
        return False
    tail_dates = [old_group[-1].date, *[t.date for t in candidate]]
    return _gaps_match_rule(tail_dates, rule)


def _yearly_cost(amount: Decimal, rule: PeriodRule) -> Decimal:
    return (amount * rule.charges_per_year).quantize(_CENT, rounding=ROUND_HALF_UP)


def _is_active(last_date: Date, statement_end: Date, rule: PeriodRule) -> bool:
    days_since = Decimal((statement_end - last_date).days)
    return days_since <= rule.period_days * ACTIVE_MAX_PERIODS


def _fmt_money(amount: Decimal) -> str:
    return f"${amount:.2f}"


def _make_recurring_flag(
    group: list[Transaction], rule: PeriodRule, statement_end: Date
) -> RecurringFlag:
    ordered = sorted(group, key=lambda t: (t.date, t.line))
    latest = ordered[-1]
    first_date, last_date = ordered[0].date, latest.date
    active = _is_active(last_date, statement_end, rule)
    yearly_cost = _yearly_cost(latest.amount, rule) if active else None
    reason = _recurring_reason(
        latest.description,
        latest.amount,
        rule,
        len(ordered),
        first_date,
        last_date,
        active,
        yearly_cost,
    )
    return RecurringFlag(
        type="recurring",
        lines=tuple(t.line for t in ordered),
        merchant=latest.description,
        period=rule.name,
        active=active,
        amount=latest.amount,
        count=len(ordered),
        first_date=first_date,
        last_date=last_date,
        yearly_cost=yearly_cost,
        reason=reason,
    )


def _recurring_reason(
    merchant: str,
    amount: Decimal,
    rule: PeriodRule,
    count: int,
    first_date: Date,
    last_date: Date,
    active: bool,
    yearly_cost: Decimal | None,
) -> str:
    money = _fmt_money(amount)
    if not active:
        return (
            f"{merchant}: {money} charged {_STOPPED_PHRASE[rule.name]}, {count} times. "
            f"The last charge was {last_date.isoformat()}, so it seems to have stopped."
        )
    assert yearly_cost is not None
    if rule.name == "yearly" and count == 2:
        return (
            f"{merchant}: {money} charged twice, a year apart "
            f"({first_date.isoformat()} and {last_date.isoformat()}). "
            f"About {_fmt_money(yearly_cost)} a year if it continues."
        )
    return (
        f"{merchant}: {money} charged {_ACTIVE_PHRASE[rule.name]}, {count} times "
        f"from {first_date.isoformat()} to {last_date.isoformat()}. "
        f"About {_fmt_money(yearly_cost)} a year at the latest price."
    )


def _make_price_flag(
    candidate: Sequence[Transaction], old_amount: Decimal, new_amount: Decimal, rule: PeriodRule
) -> PriceIncreaseFlag:
    ordered = sorted(candidate, key=lambda t: (t.date, t.line))
    start_date = ordered[0].date
    pct = round((new_amount - old_amount) / old_amount * 100)
    yearly_diff = _yearly_cost(new_amount - old_amount, rule)
    reason = (
        f"{ordered[-1].description} went from {_fmt_money(old_amount)} to {_fmt_money(new_amount)} "
        f"({pct}% more) starting {start_date.isoformat()}. "
        f"At the new price that adds about {_fmt_money(yearly_diff)} a year."
    )
    return PriceIncreaseFlag(
        type="price_increase",
        lines=tuple(t.line for t in ordered),
        merchant=ordered[-1].description,
        period=rule.name,
        old_amount=old_amount,
        new_amount=new_amount,
        reason=reason,
    )
