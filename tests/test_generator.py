"""Data tests on the synthetic statement generator (docs/eval_plan.md).

These run only on the tuning seeds (0 to 99), never the test seeds, per the freeze
rule in `docs/eval_plan.md`. They check the generator's own output is internally
consistent: reproducible, inside the ranges the plan sets, and readable by the real
importer with no skipped rows.
"""

from __future__ import annotations

import csv
import io
from decimal import Decimal
from typing import Any

import pytest

from evaluation.common import is_close_amount
from evaluation.generator import generate_statement
from second_look.importer import parse_transactions
from second_look.thresholds import PERIOD_RULES

TUNING_SEEDS = range(0, 100)
PERIOD_BY_NAME = {r.name: r for r in PERIOD_RULES}


def _generate(seed: int) -> tuple[str, Any, dict[str, Any]]:
    return generate_statement(seed, stress=False)


@pytest.mark.parametrize("seed", [0, 1, 7, 42, 99])
def test_same_seed_is_byte_identical(seed: int) -> None:
    csv_a, _, key_a = _generate(seed)
    csv_b, _, key_b = _generate(seed)
    assert csv_a == csv_b
    assert key_a == key_b


@pytest.mark.parametrize("seed", TUNING_SEEDS)
def test_importer_reads_every_row(seed: int) -> None:
    csv_text, mapping, _ = _generate(seed)
    rows = list(csv.reader(io.StringIO(csv_text)))
    result = parse_transactions(rows, mapping)
    assert result.summary.skipped == ()
    assert result.summary.rows_used == result.summary.rows_read - 1  # header


@pytest.mark.parametrize("seed", TUNING_SEEDS)
def test_lengths_and_dates_are_in_range(seed: int) -> None:
    _, _, key = _generate(seed)
    first = key["first_date"]
    last = key["last_date"]
    assert "2023-01-01" <= first
    assert first <= "2024-12-31"
    assert first < last


@pytest.mark.parametrize("seed", TUNING_SEEDS)
def test_account_type_matches_seed_parity(seed: int) -> None:
    _, _, key = _generate(seed)
    expected = "credit" if seed % 2 else "chequing"
    assert key["account_type"] == expected


@pytest.mark.parametrize("seed", TUNING_SEEDS)
def test_every_line_in_the_answer_key_exists_and_amount_matches(seed: int) -> None:
    csv_text, mapping, key = _generate(seed)
    rows = list(csv.reader(io.StringIO(csv_text)))
    result = parse_transactions(rows, mapping)
    by_line = {t.line: t for t in result.transactions}
    total_lines = len(rows)

    for event in key["events"]:
        if "lines" in event:
            lines = event["lines"]
        elif event["type"] == "price_increase":
            lines = [event["first_new_line"]]
        else:
            lines = [event["line"]]
        for line in lines:
            assert 2 <= line <= total_lines, f"{event['id']} points at a missing line {line}"
            assert line in by_line, f"{event['id']}'s line {line} was skipped by the importer"

        if event["type"] == "price_increase":
            txn = by_line[event["first_new_line"]]
            assert is_close_amount(txn.amount, Decimal(event["new_amount"]))
        elif event["type"] == "duplicate":
            original, copy = (by_line[line] for line in event["lines"])
            assert original.amount == copy.amount
        elif event["type"] == "decoy" and event["kind"] == "refunded_duplicate_refund":
            assert by_line[event["line"]].amount < 0


@pytest.mark.parametrize("seed", TUNING_SEEDS)
def test_no_line_belongs_to_two_events_except_a_price_increase(seed: int) -> None:
    _, _, key = _generate(seed)
    owner: dict[int, str] = {}
    for event in key["events"]:
        if event["type"] == "price_increase":
            continue  # a price increase sits inside its own recurring series on purpose
        lines = event["lines"] if "lines" in event else [event["line"]]
        for line in lines:
            assert line not in owner, (
                f"line {line} belongs to both {owner.get(line)} and {event['id']}"
            )
            owner[line] = event["id"]


@pytest.mark.parametrize("seed", TUNING_SEEDS)
def test_planted_series_meet_the_adr_0002_windows_and_minimum_counts(seed: int) -> None:
    csv_text, mapping, key = _generate(seed)
    rows = list(csv.reader(io.StringIO(csv_text)))
    result = parse_transactions(rows, mapping)
    by_line = {t.line: t for t in result.transactions}

    for event in key["events"]:
        if event["type"] != "recurring":
            continue
        rule = PERIOD_BY_NAME[event["period"]]
        dates = sorted(by_line[line].date for line in event["lines"])
        assert len(dates) >= rule.min_charges
        gaps = [(b - a).days for a, b in zip(dates, dates[1:], strict=False)]
        for gap in gaps:
            in_window = rule.gap_low_days <= gap <= rule.gap_high_days
            in_skip_window = (
                rule.allow_one_skip and 2 * rule.gap_low_days <= gap <= 2 * rule.gap_high_days
            )
            assert in_window or in_skip_window, f"{event['id']} has a gap of {gap} days"


@pytest.mark.parametrize("seed", TUNING_SEEDS)
def test_amounts_and_counts_are_inside_the_planned_ranges(seed: int) -> None:
    _, _, key = _generate(seed)
    subs = [e for e in key["events"] if e["type"] == "recurring" and e["kind"] == "fixed"]
    # 3 to 8 subscriptions are drawn, plus rent (chequing only). The varying bill is
    # "variable". A drawn subscription is only planted if it still meets the ADR 0002
    # minimum count after its variations (docs/eval_plan.md, "Planted recurring
    # charges"), so the number actually planted can be fewer than 3, never more than 8.
    subscription_count = len(subs) - (1 if key["account_type"] == "chequing" else 0)
    assert 0 <= subscription_count <= 8
    for event in key["events"]:
        if event["type"] == "unusual" and event["kind"] == "spike_known_merchant":
            assert 3.0 <= event["factor"] <= 10.0  # stress=False here: factor is drawn from 3 to 10
