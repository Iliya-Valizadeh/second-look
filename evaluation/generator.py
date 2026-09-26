"""Synthetic statement generator (docs/eval_plan.md).

`generate_statement(seed, stress=False, dump_dir=None)` returns `(csv_text, mapping,
answer_key)`. Each statement uses one `random.Random(seed)` object and nothing else
(ADR 0001 keeps `random` out of `src/second_look`, so this module lives here
instead). Even seeds are chequing statements, odd seeds are credit card statements.

This module writes the CSV and the answer key, but never touches a file itself
unless the caller passes `dump_dir`; the evaluation script decides what to do with
the output, the same separation ADR 0001 draws between the core engine and a door.
"""

from __future__ import annotations

import csv
import io
import json
import math
import string
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from random import Random
from typing import Any

from second_look.models import ColumnMapping, SignConvention
from second_look.thresholds import ACTIVE_MAX_PERIODS, PERIOD_RULES, PeriodRule

from . import merchants as M
from .common import (
    add_months,
    all_dates,
    calendar_months,
    days_in_month,
    decimal_median,
    round_cents,
)

GENERATOR_VERSION = "1"

PERIOD_RULE_BY_NAME: dict[str, PeriodRule] = {r.name: r for r in PERIOD_RULES}

MONTHLY_AMOUNTS = (
    "4.99",
    "7.99",
    "9.99",
    "11.99",
    "14.99",
    "16.99",
    "19.99",
    "24.99",
    "34.99",
    "49.99",
    "64.99",
    "89.99",
)
WEEKLY_AMOUNTS = ("3.99", "5.99", "8.99", "12.99", "59.99", "74.99")
YEARLY_AMOUNTS = ("39.99", "59.99", "79.99", "99.99", "119.99", "139.99")

TRANSIT_AMOUNT = Decimal("3.35")


# --- Entry and builder state -------------------------------------------------------


@dataclass
class Entry:
    id: int
    date: date
    description: str
    amount: Decimal  # positive = a charge, negative = money coming in
    category: str | None = None


@dataclass
class Builder:
    seed: int
    stress: bool
    rng: Random = field(init=False)
    account_type: str = field(init=False)
    entries: list[Entry] = field(default_factory=list)
    background_charges: dict[str, list[Entry]] = field(default_factory=dict)
    merchant_entries: dict[str, list[Entry]] = field(default_factory=dict)
    new_merchant_pool: list[str] = field(default_factory=list)
    start_date: date = field(init=False)
    end_date: date = field(init=False)
    length_months: int = field(init=False)
    months: list[tuple[date, date]] = field(default_factory=list)
    _next_id: int = 0
    _counters: dict[str, int] = field(
        default_factory=lambda: {"rec": 0, "pri": 0, "dup": 0, "unu": 0, "dec": 0}
    )

    def __post_init__(self) -> None:
        self.rng = Random(self.seed)
        self.account_type = "credit" if self.seed % 2 == 1 else "chequing"
        self.background_charges = {name: [] for name in M.BACKGROUND_CATEGORIES}
        self.new_merchant_pool = list(M.NEW_MERCHANT_NAMES)
        self.rng.shuffle(self.new_merchant_pool)

    def add_entry(
        self, dt: date, description: str, amount: Decimal, category: str | None = None
    ) -> Entry:
        entry = Entry(self._next_id, dt, description, amount, category)
        self._next_id += 1
        self.entries.append(entry)
        return entry

    def new_event_id(self, kind: str) -> str:
        self._counters[kind] += 1
        return f"{kind}-{self._counters[kind]:02d}"


# --- Top-level entry point ----------------------------------------------------------


def generate_statement(
    seed: int, stress: bool = False, dump_dir: str | Path | None = None
) -> tuple[str, ColumnMapping, dict[str, Any]]:
    b = Builder(seed=seed, stress=stress)
    _plan_length_and_dates(b)
    _plan_background_spending(b)
    _plan_payroll(b)
    series_list = _plan_recurring(b)
    decoy_events = _plan_decoys(b, series_list)
    duplicate_events = _plan_duplicates(b)
    unusual_events = _plan_unusual(b)
    _plan_card_payments(b)
    decoy_events = decoy_events + _plan_refunds(b, duplicate_events)

    csv_text, mapping, line_of = _sort_and_write(b)
    answer_key = _build_answer_key(
        b, series_list, decoy_events, duplicate_events, unusual_events, line_of
    )

    if dump_dir is not None:
        _dump(dump_dir, seed, csv_text, answer_key)
    return csv_text, mapping, answer_key


def _dump(dump_dir: str | Path, seed: int, csv_text: str, answer_key: dict[str, Any]) -> None:
    path = Path(dump_dir)
    path.mkdir(parents=True, exist_ok=True)
    (path / f"seed_{seed}.csv").write_text(csv_text, encoding="utf-8")
    (path / f"seed_{seed}_key.json").write_text(
        json.dumps(answer_key, indent=2, sort_keys=True), encoding="utf-8"
    )


# --- Length and dates ----------------------------------------------------------------


def _plan_length_and_dates(b: Builder) -> None:
    b.length_months = b.rng.randint(6, 24)
    range_start = date(2023, 1, 1)
    range_end = date(2024, 12, 31)
    offset = b.rng.randint(0, (range_end - range_start).days)
    b.start_date = range_start + timedelta(days=offset)
    b.end_date = add_months(b.start_date, b.length_months) - timedelta(days=1)
    b.months = calendar_months(b.start_date, b.end_date)


# --- Background spending -------------------------------------------------------------


def _plan_background_spending(b: Builder) -> None:
    for cat_name, cfg in M.BACKGROUND_CATEGORIES.items():
        order = list(cfg["merchants"])
        b.rng.shuffle(order)
        weights = [1 / (i + 1) for i in range(len(order))]

        store_numbers: dict[str, list[str]] = {}
        for m in order:
            if m.has_store_number:
                count = b.rng.randint(1, 3)
                store_numbers[m.name] = [str(b.rng.randint(100, 999)) for _ in range(count)]
        factors = {m.name: b.rng.uniform(0.7, 1.3) for m in order}

        for month_start, month_end in b.months:
            visits = b.rng.randint(*cfg["visits"])
            span = (month_end - month_start).days
            for _ in range(visits):
                m = b.rng.choices(order, weights=weights, k=1)[0]
                day_offset = b.rng.randint(0, span) if span > 0 else 0
                dt = month_start + timedelta(days=day_offset)
                store_num = b.rng.choice(store_numbers[m.name]) if m.name in store_numbers else None
                description = m.describe(store_num)
                if cat_name == "coffee":
                    amount = Decimal(b.rng.choice(M.COFFEE_MENU))
                else:
                    median = Decimal(cfg["median"]) * Decimal(str(factors[m.name]))
                    amount = _lognormal_amount(b.rng, median, cfg["sigma"])
                entry = b.add_entry(dt, description, amount, category=m.category)
                b.background_charges[cat_name].append(entry)
                b.merchant_entries.setdefault(m.name, []).append(entry)
    _plan_transit(b)


def _lognormal_amount(rng: Random, median: Decimal, sigma: float) -> Decimal:
    mu = math.log(float(median))
    value = rng.lognormvariate(mu, sigma)
    return round_cents(Decimal(str(value)))


def _plan_transit(b: Builder) -> None:
    description = M.TRANSIT.describe()
    d = b.start_date
    while d <= b.end_date:
        if d.weekday() < 5:
            b.add_entry(d, description, TRANSIT_AMOUNT, category=M.TRANSIT.category)
            if b.rng.random() < 0.3:
                b.add_entry(d, description, TRANSIT_AMOUNT, category=M.TRANSIT.category)
        d += timedelta(days=1)


def _plan_payroll(b: Builder) -> None:
    if b.account_type != "chequing":
        return
    amount = Decimal(b.rng.randint(1800, 3200))
    first_offset = b.rng.randint(0, 13)
    d = b.start_date + timedelta(days=first_offset)
    while d <= b.end_date:
        b.add_entry(d, "PAYROLL DEPOSIT", -amount, category=None)
        d += timedelta(days=14)


def _plan_card_payments(b: Builder) -> None:
    if b.account_type != "credit":
        return
    for i in range(len(b.months) - 1):
        m_start, m_end = b.months[i]
        total = sum(
            (e.amount for e in b.entries if e.amount > 0 and m_start <= e.date <= m_end),
            Decimal("0"),
        )
        if total <= 0:
            continue
        first_of_next = add_months(date(m_start.year, m_start.month, 1), 1)
        pay_date = date(first_of_next.year, first_of_next.month, min(20, 28))
        if b.start_date <= pay_date <= b.end_date:
            b.add_entry(pay_date, "CARD PAYMENT RECEIVED", -total, category=None)


# --- Recurring charges, price increases ----------------------------------------------


def _draw_period(rng: Random) -> str:
    return rng.choices(["monthly", "weekly", "yearly"], weights=[0.75, 0.10, 0.15], k=1)[0]


def _monthly_dates(start: date, end: date, billing_day: int) -> list[date]:
    dates = []
    cur = date(start.year, start.month, 1)
    while cur <= end:
        day = min(billing_day, days_in_month(cur.year, cur.month))
        d = date(cur.year, cur.month, day)
        if start <= d <= end:
            dates.append(d)
        cur = add_months(cur, 1)
    return dates


def _weekly_dates(start: date, end: date, weekday: int) -> list[date]:
    dates = []
    d = start + timedelta(days=(weekday - start.weekday()) % 7)
    while d <= end:
        dates.append(d)
        d += timedelta(days=7)
    return dates


def _yearly_dates(start: date, end: date, month: int, day: int) -> list[date]:
    dates = []
    year = start.year
    while True:
        try:
            d = date(year, month, day)
        except ValueError:
            d = date(year, month, 28)
        if d > end:
            break
        if d >= start:
            dates.append(d)
        year += 1
    return dates


def _apply_variations(b: Builder, dates: list[date], rule: PeriodRule) -> tuple[list[date], bool]:
    skipped_one = False
    if len(dates) < rule.min_charges:
        return dates, skipped_one

    if b.rng.random() < 0.2:  # late start
        max_trim = len(dates) - rule.min_charges
        if max_trim >= 1:
            trim = b.rng.randint(1, max_trim)
            dates = dates[trim:]

    if b.rng.random() < 0.15:  # stopped
        n = len(dates)
        valid_trims = [
            trim
            for trim in range(1, n - rule.min_charges + 1)
            if (b.end_date - dates[n - 1 - trim]).days >= 2 * rule.period_days
        ]
        if valid_trims:
            trim = b.rng.choice(valid_trims)
            dates = dates[: n - trim]

    if (
        rule.name in ("weekly", "monthly")
        and len(dates) > rule.min_charges
        and b.rng.random() < 0.10
    ):
        idx = b.rng.randint(1, len(dates) - 2)
        dates = dates[:idx] + dates[idx + 1 :]
        skipped_one = True

    return dates, skipped_one


def _build_subscription_series(b: Builder, name: str) -> dict[str, Any] | None:
    period = _draw_period(b.rng)
    if period == "yearly" and b.length_months < 13:
        period = "monthly"
    rule = PERIOD_RULE_BY_NAME[period]

    amount_pool: tuple[str, ...]
    if period == "monthly":
        billing_day = b.rng.randint(1, 31)
        base_dates = _monthly_dates(b.start_date, b.end_date, billing_day)
        amount_pool = MONTHLY_AMOUNTS
        delay_hi = 5 if b.stress else 3
    elif period == "weekly":
        weekday = b.rng.randint(0, 6)
        base_dates = _weekly_dates(b.start_date, b.end_date, weekday)
        amount_pool = WEEKLY_AMOUNTS
        delay_hi = 5 if b.stress else 1
    else:
        month = b.rng.randint(1, 12)
        day = b.rng.randint(1, 28)
        base_dates = _yearly_dates(b.start_date, b.end_date, month, day)
        amount_pool = YEARLY_AMOUNTS
        delay_hi = 5 if b.stress else 3

    base_dates, skipped_one = _apply_variations(b, base_dates, rule)
    if len(base_dates) < rule.min_charges:
        return None

    delayed = []
    for d in base_dates:
        delay = b.rng.randint(0, delay_hi)
        posted = d + timedelta(days=delay)
        if posted <= b.end_date:
            delayed.append(posted)
    if len(delayed) < rule.min_charges:
        return None

    base_amount = Decimal(b.rng.choice(amount_pool))
    reference_word = b.rng.random() < (0.20 if b.stress else 0.05)
    return {
        "name": name,
        "kind": "fixed",
        "period": period,
        "rule": rule,
        "dates": delayed,
        "amounts": [base_amount] * len(delayed),
        "foreign_currency": b.rng.random() < 0.15,
        "reference_number": b.rng.random() < 0.3,
        "reference_word": reference_word,
        "skipped_one": skipped_one,
        "eligible_for_increase": period in ("weekly", "monthly") and not reference_word,
        "price_increase": None,
    }


def _build_rent_series(b: Builder) -> dict[str, Any]:
    rule = PERIOD_RULE_BY_NAME["monthly"]
    dates = _monthly_dates(b.start_date, b.end_date, 1)
    delayed = []
    for d in dates:
        posted = d + timedelta(days=b.rng.randint(0, 2))
        if posted <= b.end_date:
            delayed.append(posted)
    amount = Decimal(b.rng.randrange(1400, 2601, 50))
    return {
        "name": M.RENT_DESCRIPTION,
        "kind": "fixed",
        "period": "monthly",
        "rule": rule,
        "dates": delayed,
        "amounts": [amount] * len(delayed),
        "foreign_currency": False,
        "reference_number": True,
        "reference_word": False,
        "skipped_one": False,
        "eligible_for_increase": False,
        "price_increase": None,
    }


def _build_varying_bill_series(b: Builder) -> dict[str, Any]:
    rule = PERIOD_RULE_BY_NAME["monthly"]
    billing_day = b.rng.randint(1, 31)
    dates = _monthly_dates(b.start_date, b.end_date, billing_day)
    delayed = []
    for d in dates:
        posted = d + timedelta(days=b.rng.randint(0, 3))
        if posted <= b.end_date:
            delayed.append(posted)
    base = Decimal(str(b.rng.uniform(60, 180)))
    amounts = [round_cents(base * Decimal(str(b.rng.uniform(0.85, 1.15)))) for _ in delayed]
    return {
        "name": M.VARYING_BILL_DESCRIPTION,
        "kind": "variable",
        "period": "monthly",
        "rule": rule,
        "dates": delayed,
        "amounts": amounts,
        "foreign_currency": False,
        "reference_number": False,
        "reference_word": False,
        "skipped_one": False,
        "eligible_for_increase": False,
        "price_increase": None,
    }


def _round_up_99(x: Decimal) -> Decimal:
    dollars = int(x // 1)
    candidate = Decimal(dollars) + Decimal("0.99")
    if candidate < x:
        candidate += 1
    return candidate


def _apply_price_increase(b: Builder, series: dict[str, Any]) -> None:
    if not series["eligible_for_increase"]:
        return
    if b.rng.random() >= 0.25:
        return
    rule: PeriodRule = series["rule"]
    dates = series["dates"]
    n = len(dates)
    candidates = [i for i in range(1, n) if i >= rule.min_charges and (n - i) >= 2]
    if not candidates:
        return
    idx = b.rng.choice(candidates)
    old_amount = series["amounts"][0]
    p = b.rng.uniform(0.05, 0.30)
    new_amount = _round_up_99(old_amount * (Decimal(1) + Decimal(str(p))))
    for i in range(idx, n):
        series["amounts"][i] = new_amount
    series["price_increase"] = {
        "first_new_line_index": idx,
        "old_amount": old_amount,
        "new_amount": new_amount,
    }


def _apply_foreign_currency(b: Builder, series: dict[str, Any]) -> None:
    if not series["foreign_currency"]:
        return
    lo, hi = (0.975, 1.025) if b.stress else (0.99, 1.01)
    series["amounts"] = [
        round_cents(a * Decimal(str(b.rng.uniform(lo, hi)))) for a in series["amounts"]
    ]


def _format_description(
    b: Builder, base_name: str, reference_number: bool, reference_word: bool
) -> str:
    if reference_word:
        code = "".join(b.rng.choice(string.ascii_uppercase) for _ in range(3))
        return f"{base_name} {code}"
    if reference_number:
        num = "".join(b.rng.choice(string.digits) for _ in range(8))
        return f"{base_name} {num}"
    return base_name


def _materialize_series(b: Builder, series: dict[str, Any], category: str | None) -> None:
    entries = []
    for d, amt in zip(series["dates"], series["amounts"], strict=True):
        desc = _format_description(
            b, series["name"], series["reference_number"], series["reference_word"]
        )
        entries.append(b.add_entry(d, desc, amt, category=category))
    series["entries"] = entries


def _plan_recurring(b: Builder) -> list[dict[str, Any]]:
    series_list: list[dict[str, Any]] = []

    count = b.rng.randint(3, 8)
    names = list(M.SUBSCRIPTION_MERCHANTS)
    b.rng.shuffle(names)
    for name in names[:count]:
        series = _build_subscription_series(b, name)
        if series is None:
            continue
        _apply_price_increase(b, series)
        _apply_foreign_currency(b, series)
        _materialize_series(b, series, category="Subscriptions")
        series_list.append(series)

    if b.account_type == "chequing":
        rent = _build_rent_series(b)
        _materialize_series(b, rent, category="Rent")
        series_list.append(rent)

    bill = _build_varying_bill_series(b)
    _materialize_series(b, bill, category="Bills")
    series_list.append(bill)

    return series_list


# --- Decoys --------------------------------------------------------------------------


def _plan_decoys(b: Builder, series_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
    decoys = []
    for series in series_list:
        if series["kind"] != "fixed" or series["period"] not in ("weekly", "monthly"):
            continue
        if series["name"] == M.RENT_DESCRIPTION:
            continue
        if b.rng.random() >= 0.10:
            continue
        base_amount = series["amounts"][0]
        factor = Decimal(str(b.rng.uniform(1.2, 2.0)))
        amount = round_cents(base_amount * factor)
        existing = series["dates"]
        candidates = [
            d
            for d in all_dates(b.start_date, b.end_date)
            if all(abs((d - ed).days) >= 3 for ed in existing)
        ]
        if not candidates:
            continue
        d = b.rng.choice(candidates)
        desc = _format_description(
            b, series["name"], series["reference_number"], series["reference_word"]
        )
        entry = b.add_entry(d, desc, amount, category="Subscriptions")
        decoys.append({"kind": "one_off_extra", "entry": entry})
    return decoys


# --- Duplicates ------------------------------------------------------------------------


def _plan_duplicates(b: Builder) -> list[dict[str, Any]]:
    duplicate_events = []
    count = b.rng.randint(0, 3)
    pool = [e for cat in M.DUPLICATE_SPIKE_CATEGORIES for e in b.background_charges[cat]]
    for _ in range(count):
        if not pool:
            break
        original = b.rng.choice(pool)
        delay = b.rng.randint(0, 2)
        copy_date = original.date + timedelta(days=delay)
        if copy_date > b.end_date:
            continue
        copy_entry = b.add_entry(
            copy_date, original.description, original.amount, category=original.category
        )
        duplicate_events.append({"original": original, "copy": copy_entry, "refunded": False})
    return duplicate_events


# --- Unusual charges ---------------------------------------------------------------------


def _plan_unusual(b: Builder) -> list[dict[str, Any]]:
    events = []
    count = b.rng.randint(1, 4)
    for _ in range(count):
        event = None
        if b.rng.random() < 0.6:
            event = _plan_spike(b)
        if event is None:
            event = _plan_new_merchant(b)
        if event is not None:
            events.append(event)
    return events


def _plan_spike(b: Builder) -> dict[str, Any] | None:
    eligible = [name for name, es in b.merchant_entries.items() if len(es) >= 6]
    b.rng.shuffle(eligible)
    lo, hi = (2, 5) if b.stress else (3, 10)
    for name in eligible:
        charges = b.merchant_entries[name]
        median = decimal_median(c.amount for c in charges)
        factor = Decimal(str(b.rng.uniform(lo, hi)))
        amount = round_cents(median * factor)
        if amount < Decimal("25"):
            continue
        span = (b.end_date - b.start_date).days
        day_offset = b.rng.randint(0, span) if span > 0 else 0
        d = b.start_date + timedelta(days=day_offset)
        sample = b.rng.choice(charges)
        entry = b.add_entry(d, sample.description, amount, category=sample.category)
        return {"kind": "spike_known_merchant", "entry": entry, "factor": float(factor)}
    return None


def _plan_new_merchant(b: Builder) -> dict[str, Any] | None:
    if not b.new_merchant_pool:
        return None
    name = b.new_merchant_pool.pop(0)
    amount = round_cents(Decimal(str(b.rng.uniform(150, 900))))
    span = (b.end_date - b.start_date).days
    if span < 60:
        return None
    day_offset = b.rng.randint(60, span)
    d = b.start_date + timedelta(days=day_offset)
    entry = b.add_entry(d, name, amount, category="Shopping")
    return {"kind": "large_new_merchant", "entry": entry}


# --- Refunds ---------------------------------------------------------------------------


def _plan_refunds(b: Builder, duplicate_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    decoys = []
    for e in list(b.background_charges["shopping"]):
        if b.rng.random() < 0.05:
            days = b.rng.randint(3, 20)
            refund_date = e.date + timedelta(days=days)
            if refund_date <= b.end_date:
                b.add_entry(refund_date, e.description, -e.amount, category=e.category)

    for dup in duplicate_events:
        copy = dup["copy"]
        can_refund = (b.end_date - copy.date).days >= 10
        if can_refund and b.rng.random() < 0.3:
            days = b.rng.randint(3, 10)
            refund_date = copy.date + timedelta(days=days)
            if refund_date <= b.end_date:
                refund_entry = b.add_entry(
                    refund_date, copy.description, -copy.amount, category=copy.category
                )
                dup["refunded"] = True
                decoys.append({"kind": "refunded_duplicate_refund", "entry": refund_entry})
    return decoys


# --- Sorting, writing, and the answer key -----------------------------------------------


def _sort_and_write(b: Builder) -> tuple[str, ColumnMapping, dict[int, int]]:
    ordered = sorted(b.entries, key=lambda e: (e.date, e.id), reverse=(b.account_type == "credit"))

    line_of: dict[int, int] = {}
    rows: list[list[str]] = []
    if b.account_type == "chequing":
        rows.append(["Date", "Description", "Amount"])
    else:
        rows.append(["Transaction Date", "Description", "Category", "Debit", "Credit"])

    line = 2
    for e in ordered:
        line_of[e.id] = line
        if b.account_type == "chequing":
            rows.append([e.date.isoformat(), e.description, f"{-e.amount:.2f}"])
        else:
            date_str = e.date.strftime("%m/%d/%Y")
            category = e.category or ""
            if e.amount > 0:
                debit, credit = f"{e.amount:.2f}", ""
            else:
                debit, credit = "", f"{-e.amount:.2f}"
            rows.append([date_str, e.description, category, debit, credit])
        line += 1

    buf = io.StringIO(newline="")
    csv.writer(buf, lineterminator="\n").writerows(rows)
    csv_text = buf.getvalue()

    if b.account_type == "chequing":
        mapping = ColumnMapping(
            has_header=True,
            date_column="Date",
            date_format="YYYY-MM-DD",
            description_columns=("Description",),
            amount_column="Amount",
            sign_convention=SignConvention.CHARGES_NEGATIVE,
        )
    else:
        mapping = ColumnMapping(
            has_header=True,
            date_column="Transaction Date",
            date_format="MM/DD/YYYY",
            description_columns=("Description",),
            category_column="Category",
            debit_column="Debit",
            credit_column="Credit",
        )
    return csv_text, mapping, line_of


def _series_active(series: dict[str, Any], statement_end: date) -> bool:
    rule: PeriodRule = series["rule"]
    last: date = series["dates"][-1]
    max_gap = float(ACTIVE_MAX_PERIODS) * rule.period_days
    return bool((statement_end - last).days <= max_gap)


def _yearly_cost(amount: Decimal, rule: PeriodRule) -> Decimal:
    return round_cents(amount * rule.charges_per_year)


def _build_answer_key(
    b: Builder,
    series_list: list[dict[str, Any]],
    decoy_events: list[dict[str, Any]],
    duplicate_events: list[dict[str, Any]],
    unusual_events: list[dict[str, Any]],
    line_of: dict[int, int],
) -> dict[str, Any]:
    events: list[dict[str, Any]] = []

    for series in series_list:
        lines = sorted(line_of[e.id] for e in series["entries"])
        rec_id = b.new_event_id("rec")
        active = _series_active(series, b.end_date)
        event: dict[str, Any] = {
            "id": rec_id,
            "type": "recurring",
            "kind": series["kind"],
            "period": series["period"],
            "lines": lines,
            "active": active,
        }
        if series["kind"] == "fixed":
            event["expected_yearly_cost"] = (
                str(_yearly_cost(series["amounts"][-1], series["rule"])) if active else None
            )
            event["foreign_currency"] = series["foreign_currency"]
            event["skipped_one"] = series["skipped_one"]
            event["reference_number"] = series["reference_number"]
            event["reference_word"] = series["reference_word"]
        events.append(event)

        pri = series.get("price_increase")
        if pri:
            pri_id = b.new_event_id("pri")
            first_new_line = line_of[series["entries"][pri["first_new_line_index"]].id]
            events.append(
                {
                    "id": pri_id,
                    "type": "price_increase",
                    "series": rec_id,
                    "old_amount": str(pri["old_amount"]),
                    "new_amount": str(pri["new_amount"]),
                    "first_new_line": first_new_line,
                }
            )

    for dec in decoy_events:
        dec_id = b.new_event_id("dec")
        events.append(
            {"id": dec_id, "type": "decoy", "kind": dec["kind"], "line": line_of[dec["entry"].id]}
        )

    for dup in duplicate_events:
        dup_id = b.new_event_id("dup")
        events.append(
            {
                "id": dup_id,
                "type": "duplicate",
                "lines": [line_of[dup["original"].id], line_of[dup["copy"].id]],
                "refunded": dup["refunded"],
            }
        )

    for unu in unusual_events:
        unu_id = b.new_event_id("unu")
        event = {
            "id": unu_id,
            "type": "unusual",
            "kind": unu["kind"],
            "line": line_of[unu["entry"].id],
        }
        if "factor" in unu:
            event["factor"] = unu["factor"]
        events.append(event)

    return {
        "seed": b.seed,
        "generator_version": GENERATOR_VERSION,
        "stress": b.stress,
        "account_type": b.account_type,
        "first_date": b.start_date.isoformat(),
        "last_date": b.end_date.isoformat(),
        "events": events,
    }
