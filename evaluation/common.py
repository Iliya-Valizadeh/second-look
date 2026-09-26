"""Small date and money helpers shared by the generator, baselines and matching.

Kept separate from `second_look` because ADR 0001 forbids `random` and file I/O in
the core package; these helpers themselves do neither, but they exist for the
evaluation code, not the engine, so they live here.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from second_look.thresholds import SAME_AMOUNT_ABS, SAME_AMOUNT_REL

CENT = Decimal("0.01")


def round_cents(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def close_amount_tolerance(a: Decimal, b: Decimal) -> Decimal:
    """The ADR 0002 close-amount tolerance: the larger of the flat cent floor and the
    percentage of the smaller amount."""
    return max(SAME_AMOUNT_ABS, SAME_AMOUNT_REL * min(a, b))


def is_close_amount(a: Decimal, b: Decimal) -> bool:
    return abs(a - b) <= close_amount_tolerance(a, b)


def days_in_month(year: int, month: int) -> int:
    if month == 12:
        nxt = date(year + 1, 1, 1)
    else:
        nxt = date(year, month + 1, 1)
    return (nxt - date(year, month, 1)).days


def add_months(d: date, months: int) -> date:
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    day = min(d.day, days_in_month(year, month))
    return date(year, month, day)


def calendar_months(start: date, end: date) -> list[tuple[date, date]]:
    """Every calendar month that `[start, end]` touches, clipped to that range."""
    months = []
    cur = date(start.year, start.month, 1)
    while cur <= end:
        nxt = add_months(cur, 1)
        month_start = max(cur, start)
        month_end = min(nxt - timedelta(days=1), end)
        months.append((month_start, month_end))
        cur = nxt
    return months


def all_dates(start: date, end: date) -> Iterator[date]:
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def decimal_median(values: Iterable[Decimal]) -> Decimal:
    vals = sorted(values)
    n = len(vals)
    mid = n // 2
    if n % 2:
        return Decimal(vals[mid])
    return Decimal((vals[mid - 1] + vals[mid]) / 2)
