"""The error analysis must account for every wrong flag and every miss the evaluation
counts, no more and no fewer. It runs on a few tuning seeds (docs/eval_plan.md keeps
the test seeds for the reported run)."""

from __future__ import annotations

from typing import Any

import pytest

from evaluation.error_analysis import run
from evaluation.evaluate import evaluate_statement

SEEDS = range(0, 4)


@pytest.fixture(scope="module")
def analysis() -> dict[str, Any]:
    return run(SEEDS)


@pytest.fixture(scope="module")
def engine_counts() -> dict[str, dict[str, int]]:
    totals: dict[str, dict[str, int]] = {}
    for seed in SEEDS:
        record = evaluate_statement(seed)
        for flag_type, by_method in record["counts"].items():
            c = by_method["engine"]
            t = totals.setdefault(flag_type, {"wrong": 0, "misses": 0})
            t["wrong"] += c["flags"] - c["hits"]
            t["misses"] += c["events"] - c["hits_recall"]
    return totals


def test_every_wrong_recurring_flag_is_sorted_once(
    analysis: dict[str, Any], engine_counts: dict[str, dict[str, int]]
) -> None:
    assert (
        sum(analysis["recurring"]["wrong_by_source"].values())
        == engine_counts["recurring"]["wrong"]
    )
    assert (
        sum(analysis["recurring"]["misses_by_cause"].values())
        == engine_counts["recurring"]["misses"]
    )


def test_every_unusual_error_is_sorted_once(
    analysis: dict[str, Any], engine_counts: dict[str, dict[str, int]]
) -> None:
    unusual = analysis["unusual"]
    assert sum(unusual["wrong_by_rule"].values()) == engine_counts["unusual"]["wrong"]
    assert sum(unusual["wrong_by_charge"].values()) == engine_counts["unusual"]["wrong"]
    assert sum(unusual["misses_by_cause"].values()) == engine_counts["unusual"]["misses"]


def test_price_increase_and_duplicate_errors_are_sorted_once(
    analysis: dict[str, Any], engine_counts: dict[str, dict[str, int]]
) -> None:
    assert analysis["price_increase"]["wrong_flags"] == engine_counts["price_increase"]["wrong"]
    assert (
        sum(analysis["price_increase"]["misses_by_cause"].values())
        == engine_counts["price_increase"]["misses"]
    )
    assert (
        sum(analysis["duplicate"]["wrong_by_source"].values())
        == engine_counts["duplicate"]["wrong"]
    )
    assert (
        sum(analysis["duplicate"]["misses_by_cause"].values())
        == engine_counts["duplicate"]["misses"]
    )


def test_the_output_names_the_seeds_it_ran_on(analysis: dict[str, Any]) -> None:
    assert analysis["test_seeds"] == {"first": 0, "last": 3, "statements": 4}
