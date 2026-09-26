"""Run the synthetic evaluation and write `reports/metrics.json` and the headline
chart (docs/eval_plan.md).

`python -m evaluation.evaluate` (via `make eval`) is the only way this file is meant
to be run. It generates the test statements at the seeds and rates the plan fixes,
runs the real engine and the baselines on each one, matches flags to planted events,
and writes the metrics and the chart. Nothing here is committed except the outputs.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Any, cast

from second_look.duplicate import detect_duplicates
from second_look.importer import parse_transactions
from second_look.models import Flag, RecurringFlag, Transaction
from second_look.recurring import detect_recurring
from second_look.unusual import detect_unusual

from . import matching, metrics
from .baselines import (
    baseline_duplicate,
    baseline_price_increase,
    baseline_recurring,
    baseline_unusual,
)
from .generator import GENERATOR_VERSION, generate_statement

REPO_ROOT = Path(__file__).resolve().parent.parent
METRICS_PATH = REPO_ROOT / "reports" / "metrics.json"
FIGURE_PATH = REPO_ROOT / "reports" / "figures" / "headline.png"
FIRST_RUN_PATH = REPO_ROOT / "reports" / "metrics_first_run.json"
FIRST_RUN_COMMIT = "f532add"
"""The commit whose `reports/metrics.json` was the first test run. The eval plan's freeze
rule says that run is always reported, so `run()` copies it, unchanged, into the
`first_run` key of every later result. `FIRST_RUN_PATH` is that file, byte for byte."""

TEST_SEED_FIRST = 1000
TEST_SEED_LAST = 1199
BOOTSTRAP_RESAMPLES = 2000
BOOTSTRAP_SEED = 4242

FLAG_TYPES = ("recurring", "price_increase", "duplicate", "unusual")


def _flag_to_dict(flag: Flag) -> dict[str, Any]:
    d: dict[str, Any] = {"lines": tuple(flag.lines)}
    if flag.type == "price_increase":
        d["new_amount"] = flag.new_amount
    return d


def _run_engine(
    transactions: Sequence[Transaction], statement_end: date
) -> dict[str, Sequence[Flag]]:
    recurring_flags, price_flags = detect_recurring(transactions, statement_end)
    duplicate_flags = detect_duplicates(transactions, recurring_flags)
    unusual_flags = detect_unusual(transactions, recurring_flags)
    return {
        "recurring": recurring_flags,
        "price_increase": price_flags,
        "duplicate": duplicate_flags,
        "unusual": unusual_flags,
    }


def _run_baselines(transactions: Sequence[Transaction]) -> dict[str, list[dict[str, Any]]]:
    rec = baseline_recurring(transactions)
    pri = baseline_price_increase(transactions, rec)
    dup = baseline_duplicate(transactions)
    unu = baseline_unusual(transactions)
    return {"recurring": rec, "price_increase": pri, "duplicate": dup, "unusual": unu}


def evaluate_statement(seed: int, stress: bool = False) -> dict[str, Any]:
    csv_text, mapping, answer_key = generate_statement(seed, stress=stress)
    rows = list(csv.reader(io.StringIO(csv_text)))
    import_result = parse_transactions(rows, mapping)
    transactions = import_result.transactions
    statement_end = max((t.date for t in transactions), default=date(2023, 1, 1))

    engine_raw = _run_engine(transactions, statement_end)
    baseline_raw = _run_baselines(transactions)

    events = answer_key["events"]
    rec_events = [e for e in events if e["type"] == "recurring"]
    rec_fixed = [e for e in rec_events if e["kind"] == "fixed"]
    rec_variable = [e for e in rec_events if e["kind"] == "variable"]
    rec_ref_word = [e for e in rec_fixed if e.get("reference_word")]
    pri_events = [e for e in events if e["type"] == "price_increase"]
    dup_events = [e for e in events if e["type"] == "duplicate"]
    dup_unrefunded = [e for e in dup_events if not e["refunded"]]
    dup_refunded = [e for e in dup_events if e["refunded"]]
    unu_events = [e for e in events if e["type"] == "unusual"]

    pools = {
        "recurring": (rec_events, rec_fixed, matching.match_recurring),
        "price_increase": (pri_events, pri_events, matching.match_price_increase),
        "duplicate": (dup_events, dup_unrefunded, matching.match_duplicate),
        "unusual": (unu_events, unu_events, matching.match_unusual),
    }

    counts: dict[str, dict[str, dict[str, int]]] = {}
    hit_index: dict[str, dict[str, list[tuple[int, str]]]] = {}
    for flag_type, (event_pool, recall_pool, match_fn) in pools.items():
        recall_ids = {e["id"] for e in recall_pool}
        counts[flag_type] = {}
        hit_index[flag_type] = {}
        for method in ("engine", "baseline"):
            flag_dicts: list[dict[str, Any]]
            if method == "engine":
                flag_dicts = [_flag_to_dict(f) for f in engine_raw[flag_type]]
            else:
                flag_dicts = baseline_raw[flag_type]
            hits, _, _ = match_fn(flag_dicts, event_pool)
            hits_recall = sum(1 for _, eid in hits if eid in recall_ids)
            counts[flag_type][method] = {
                "flags": len(flag_dicts),
                "hits": len(hits),
                "events": len(recall_pool),
                "hits_recall": hits_recall,
            }
            hit_index[flag_type][method] = hits

    events_by_id = {e["id"]: e for e in events}

    # Secondary: recurring hit quality (period, active status, yearly cost), among
    # engine hits that count for recall (fixed series only).
    right_period = right_active = right_cost = 0
    n_quality_hits = 0
    for fi, eid in hit_index["recurring"]["engine"]:
        event = events_by_id[eid]
        if event["kind"] != "fixed":
            continue
        flag = cast(RecurringFlag, engine_raw["recurring"][fi])
        n_quality_hits += 1
        if flag.period == event["period"]:
            right_period += 1
        if flag.active == event["active"]:
            right_active += 1
            if event["active"] and event.get("expected_yearly_cost") is not None:
                if str(flag.yearly_cost) == event["expected_yearly_cost"]:
                    right_cost += 1

    # Secondary: recall on variable series and on reference-word series.
    variable_ids = {e["id"] for e in rec_variable}
    ref_word_ids = {e["id"] for e in rec_ref_word}
    variable_hits = sum(1 for _, eid in hit_index["recurring"]["engine"] if eid in variable_ids)
    ref_word_hits = sum(1 for _, eid in hit_index["recurring"]["engine"] if eid in ref_word_ids)

    # Secondary: refunded duplicates that got an engine flag anyway.
    engine_dup_line_sets = {frozenset(f.lines) for f in engine_raw["duplicate"]}
    refunded_flagged = sum(1 for e in dup_refunded if frozenset(e["lines"]) in engine_dup_line_sets)

    return {
        "seed": seed,
        "account_type": answer_key["account_type"],
        "counts": counts,
        "event_totals": {
            "recurring_fixed": len(rec_fixed),
            "recurring_variable": len(rec_variable),
            "price_increase": len(pri_events),
            "duplicate": len(dup_unrefunded),
            "duplicate_refunded": len(dup_refunded),
            "unusual": len(unu_events),
        },
        "secondary_raw": {
            "n_quality_hits": n_quality_hits,
            "right_period": right_period,
            "right_active": right_active,
            "right_cost": right_cost,
            "variable_events": len(rec_variable),
            "variable_hits": variable_hits,
            "ref_word_events": len(rec_ref_word),
            "ref_word_hits": ref_word_hits,
            "refunded_duplicates": len(dup_refunded),
            "refunded_flagged": refunded_flagged,
        },
    }


def _safe_ratio(n: int, d: int) -> float:
    return round(n / d, 4) if d else 0.0


def _by_account_type(records: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for account_type in ("chequing", "credit"):
        indexes = [i for i, r in enumerate(records) if r["account_type"] == account_type]
        type_out: dict[str, Any] = {}
        for flag_type in FLAG_TYPES:
            for method in ("engine", "baseline"):
                pooled = metrics.pooled_counts(records, indexes, flag_type, method)
                type_out.setdefault(flag_type, {})[method] = {
                    "precision": round(pooled["precision"], 4)
                    if pooled["precision"] is not None
                    else None,
                    "recall": round(pooled["recall"], 4) if pooled["recall"] is not None else None,
                }
        out[account_type] = type_out
    return out


def _stress_report(seeds: range) -> dict[str, Any]:
    records = [evaluate_statement(seed, stress=True) for seed in seeds]
    out: dict[str, Any] = {}
    for flag_type in FLAG_TYPES:
        pooled = metrics.pooled_counts(records, range(len(records)), flag_type, "engine")
        out[flag_type] = {
            "precision": round(pooled["precision"], 4) if pooled["precision"] is not None else None,
            "recall": round(pooled["recall"], 4) if pooled["recall"] is not None else None,
            "flags": pooled["flags"],
            "hits": pooled["hits"],
            "events": pooled["events"],
        }
    return out


def _failure_bar(
    engine: dict[str, Any], f1_difference: dict[str, Any], records: list[dict[str, Any]]
) -> dict[str, Any]:
    failed: list[str] = []

    def check(flag_type: str, min_recall: float, min_precision: float) -> None:
        recall = engine[flag_type]["recall"]["value"]
        precision = engine[flag_type]["precision"]["value"]
        if recall < min_recall:
            failed.append(f"{flag_type}: recall {recall} below {min_recall}")
        if precision < min_precision:
            failed.append(f"{flag_type}: precision {precision} below {min_precision}")

    check("recurring", 0.90, 0.90)
    check("price_increase", 0.80, 0.80)
    check("duplicate", 0.80, 0.50)
    check("unusual", 0.50, 0.50)

    for flag_type in FLAG_TYPES:
        ci_low = f1_difference[flag_type]["ci_low"]
        if ci_low <= 0:
            failed.append(
                f"{flag_type}: engine F1 minus baseline F1 interval does not lie above zero "
                f"(ci_low {ci_low})"
            )

    n = len(records)
    total_wrong_per_statement = (
        sum(
            sum(
                records[i]["counts"][flag_type]["engine"]["flags"]
                - records[i]["counts"][flag_type]["engine"]["hits"]
                for flag_type in FLAG_TYPES
            )
            for i in range(n)
        )
        / n
    )
    if total_wrong_per_statement > 5:
        failed.append(
            f"all flags: {round(total_wrong_per_statement, 4)} wrong flags per statement, above 5"
        )

    return {
        "passed": len(failed) == 0,
        "failed_checks": failed,
        "wrong_flags_per_statement": round(total_wrong_per_statement, 4),
    }


def _round_floats(obj: Any) -> Any:
    if isinstance(obj, float):
        return round(obj, 4)
    if isinstance(obj, dict):
        return {k: _round_floats(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_round_floats(v) for v in obj]
    return obj


def run() -> dict[str, Any]:
    test_seeds = range(TEST_SEED_FIRST, TEST_SEED_LAST + 1)
    records = [evaluate_statement(seed, stress=False) for seed in test_seeds]

    bootstrapped = metrics.bootstrap(records, resamples=BOOTSTRAP_RESAMPLES, seed=BOOTSTRAP_SEED)
    engine_out = bootstrapped["engine"]
    baseline_out = bootstrapped["baseline"]
    f1_difference = bootstrapped["f1_difference"]

    event_totals = {
        key: sum(r["event_totals"][key] for r in records)
        for key in (
            "recurring_fixed",
            "recurring_variable",
            "price_increase",
            "duplicate",
            "duplicate_refunded",
            "unusual",
        )
    }

    sec = {
        key: sum(r["secondary_raw"][key] for r in records)
        for key in (
            "n_quality_hits",
            "right_period",
            "right_active",
            "right_cost",
            "variable_events",
            "variable_hits",
            "ref_word_events",
            "ref_word_hits",
            "refunded_duplicates",
            "refunded_flagged",
        )
    }
    secondary = {
        "recurring_hit_quality": {
            "n_hits": sec["n_quality_hits"],
            "right_period": _safe_ratio(sec["right_period"], sec["n_quality_hits"]),
            "right_active_status": _safe_ratio(sec["right_active"], sec["n_quality_hits"]),
            "right_yearly_cost": _safe_ratio(sec["right_cost"], sec["n_quality_hits"]),
        },
        "recurring_variable_recall": {
            "events": sec["variable_events"],
            "hits": sec["variable_hits"],
            "recall": _safe_ratio(sec["variable_hits"], sec["variable_events"]),
        },
        "recurring_reference_word_recall": {
            "events": sec["ref_word_events"],
            "hits": sec["ref_word_hits"],
            "recall": _safe_ratio(sec["ref_word_hits"], sec["ref_word_events"]),
        },
        "refunded_duplicates_flagged": {
            "total_refunded": sec["refunded_duplicates"],
            "flagged_anyway": sec["refunded_flagged"],
        },
        "by_account_type": _by_account_type(records),
    }

    stress = _stress_report(test_seeds)

    headline = {
        "name": "engine.recurring.recall",
        "value": engine_out["recurring"]["recall"]["value"],
        "ci_low": engine_out["recurring"]["recall"]["ci_low"],
        "ci_high": engine_out["recurring"]["recall"]["ci_high"],
    }

    failure_bar = _failure_bar(engine_out, f1_difference, records)

    result = {
        "generator_version": GENERATOR_VERSION,
        "test_seeds": {
            "first": TEST_SEED_FIRST,
            "last": TEST_SEED_LAST,
            "statements": len(records),
        },
        "interval": {
            "method": "statement_bootstrap_percentile",
            "resamples": BOOTSTRAP_RESAMPLES,
            "level": 0.95,
            "seed": BOOTSTRAP_SEED,
        },
        "events": event_totals,
        "engine": engine_out,
        "baseline": baseline_out,
        "f1_difference": f1_difference,
        "secondary": secondary,
        "stress": stress,
        "headline": headline,
        "failure_bar": failure_bar,
        "first_run": {
            "commit": FIRST_RUN_COMMIT,
            "metrics": json.loads(FIRST_RUN_PATH.read_text(encoding="utf-8")),
        },
    }
    rounded: dict[str, Any] = _round_floats(result)
    return rounded


def write_metrics(result: dict[str, Any]) -> None:
    METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    METRICS_PATH.write_text(
        json.dumps(result, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8"
    )


def draw_headline_chart(result: dict[str, Any]) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    labels = ["recurring", "price increase", "duplicate", "unusual"]
    keys = FLAG_TYPES

    engine_color = "#4C72B0"
    baseline_color = "#C4A972"

    fig, axes = plt.subplots(1, 2, figsize=(9, 4.2), sharey=True)
    for ax, metric_name, title in (
        (axes[0], "recall", "Recall"),
        (axes[1], "precision", "Precision"),
    ):
        x = range(len(keys))
        engine_vals = [result["engine"][k][metric_name]["value"] for k in keys]
        engine_err = [
            [
                result["engine"][k][metric_name]["value"]
                - result["engine"][k][metric_name]["ci_low"]
                for k in keys
            ],
            [
                result["engine"][k][metric_name]["ci_high"]
                - result["engine"][k][metric_name]["value"]
                for k in keys
            ],
        ]
        baseline_vals = [result["baseline"][k][metric_name]["value"] for k in keys]
        baseline_err = [
            [
                result["baseline"][k][metric_name]["value"]
                - result["baseline"][k][metric_name]["ci_low"]
                for k in keys
            ],
            [
                result["baseline"][k][metric_name]["ci_high"]
                - result["baseline"][k][metric_name]["value"]
                for k in keys
            ],
        ]
        width = 0.35
        ax.bar(
            [i - width / 2 for i in x],
            engine_vals,
            width,
            yerr=engine_err,
            label="engine",
            color=engine_color,
            capsize=3,
        )
        ax.bar(
            [i + width / 2 for i in x],
            baseline_vals,
            width,
            yerr=baseline_err,
            label="baseline",
            color=baseline_color,
            capsize=3,
        )
        ax.set_xticks(list(x))
        ax.set_xticklabels(labels, rotation=15)
        ax.set_ylim(0, 1.05)
        ax.set_title(title)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    axes[0].set_ylabel("share of flags or events")
    axes[0].legend(frameon=False, loc="lower left")
    fig.suptitle("Second-look: precision and recall by flag type, 200 synthetic statements")
    fig.text(
        0.5,
        -0.02,
        "Bars show the engine and the simpler baseline for each flag type, with a 95% "
        "bootstrap interval.\nThis is a synthetic test: it shows whether the rules find "
        "what was planted, not accuracy on real statements.",
        ha="center",
        fontsize=8,
        wrap=True,
    )
    fig.tight_layout(rect=(0, 0.05, 1, 1))

    FIGURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURE_PATH, dpi=150)
    plt.close(fig)


def main() -> None:
    result = run()
    write_metrics(result)
    draw_headline_chart(result)
    print(f"Wrote {METRICS_PATH}")
    print(f"Wrote {FIGURE_PATH}")
    h = result["headline"]
    print(f"Headline: recall {h['value']} ({h['ci_low']} to {h['ci_high']})")
    print(f"Failure bar passed: {result['failure_bar']['passed']}")
    if not result["failure_bar"]["passed"]:
        for check in result["failure_bar"]["failed_checks"]:
            print(f"  FAILED: {check}")


if __name__ == "__main__":
    main()
