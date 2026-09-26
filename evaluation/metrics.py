"""Precision, recall, F1 and their statement-level bootstrap intervals
(docs/eval_plan.md, "Metrics" and "Intervals").

`bootstrap(records)` takes one record per test statement (see `evaluate.py` for the
shape) and returns the engine and baseline metrics, plus the F1 difference, each
with a point value and a 95% interval from 2000 statement resamples.
"""

from __future__ import annotations

import random
from collections.abc import Iterable
from typing import Any

FLAG_TYPES = ("recurring", "price_increase", "duplicate", "unusual")
METHODS = ("engine", "baseline")


def pooled_counts(
    records: list[dict[str, Any]], indexes: Iterable[int], flag_type: str, method: str
) -> dict[str, Any]:
    flags = hits = events = hits_recall = 0
    for idx in indexes:
        c = records[idx]["counts"][flag_type][method]
        flags += c["flags"]
        hits += c["hits"]
        events += c["events"]
        hits_recall += c["hits_recall"]
    precision = hits / flags if flags else None
    recall = hits_recall / events if events else None
    if precision is None or recall is None or (precision + recall) == 0:
        f1 = None
    else:
        f1 = 2 * precision * recall / (precision + recall)
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "flags": flags,
        "hits": hits,
        "events": events,
        "hits_recall": hits_recall,
    }


def _percentile_interval(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    ordered = sorted(values)
    n = len(ordered)
    if n >= 2000:
        low_idx, high_idx = 50, 1949
    else:
        # Fewer valid draws than resamples (some were skipped): keep the same 95%
        # coverage, scaled to how many draws we actually have.
        low_idx = max(0, round(0.025 * (n - 1)))
        high_idx = min(n - 1, round(0.975 * (n - 1)))
    return ordered[low_idx], ordered[min(high_idx, n - 1)]


def bootstrap(
    records: list[dict[str, Any]], resamples: int = 2000, seed: int = 4242
) -> dict[str, Any]:
    n = len(records)
    point = {t: {m: pooled_counts(records, range(n), t, m) for m in METHODS} for t in FLAG_TYPES}

    samples: dict[str, dict[str, dict[str, list[float]]]] = {
        t: {m: {"precision": [], "recall": [], "f1": []} for m in METHODS} for t in FLAG_TYPES
    }
    skipped_f1: dict[str, dict[str, int]] = {t: {m: 0 for m in METHODS} for t in FLAG_TYPES}
    diff_samples: dict[str, list[float]] = {t: [] for t in FLAG_TYPES}

    rng = random.Random(seed)
    for _ in range(resamples):
        draw = [rng.randrange(n) for _ in range(n)]
        pooled_this_draw = {
            t: {m: pooled_counts(records, draw, t, m) for m in METHODS} for t in FLAG_TYPES
        }
        for t in FLAG_TYPES:
            for m in METHODS:
                pooled = pooled_this_draw[t][m]
                for name in ("precision", "recall", "f1"):
                    value = pooled[name]
                    if value is not None:
                        samples[t][m][name].append(value)
                if pooled["f1"] is None:
                    skipped_f1[t][m] += 1
            e_f1 = pooled_this_draw[t]["engine"]["f1"]
            b_f1 = pooled_this_draw[t]["baseline"]["f1"]
            if e_f1 is not None and b_f1 is not None:
                diff_samples[t].append(e_f1 - b_f1)

    engine_out: dict[str, dict[str, Any]] = {}
    baseline_out: dict[str, dict[str, Any]] = {}
    f1_difference: dict[str, dict[str, Any]] = {}

    for t in FLAG_TYPES:
        for m, target in (("engine", engine_out), ("baseline", baseline_out)):
            p = point[t][m]
            wrong_flags_per_statement = (
                sum(
                    records[i]["counts"][t][m]["flags"] - records[i]["counts"][t][m]["hits"]
                    for i in range(n)
                )
                / n
            )
            entry: dict[str, Any] = {
                name: {
                    "value": round(p[name] or 0.0, 4),
                    "ci_low": round(_percentile_interval(samples[t][m][name])[0], 4),
                    "ci_high": round(_percentile_interval(samples[t][m][name])[1], 4),
                }
                for name in ("precision", "recall", "f1")
            }
            entry["hits"] = p["hits"]
            entry["wrong_flags"] = p["flags"] - p["hits"]
            entry["misses"] = p["events"] - p["hits_recall"]
            entry["wrong_flags_per_statement"] = round(wrong_flags_per_statement, 4)
            entry["skipped_resamples"] = skipped_f1[t][m]
            target[t] = entry

        low, high = _percentile_interval(diff_samples[t])
        e_f1 = point[t]["engine"]["f1"] or 0.0
        b_f1 = point[t]["baseline"]["f1"] or 0.0
        f1_difference[t] = {
            "value": round(e_f1 - b_f1, 4),
            "ci_low": round(low, 4),
            "ci_high": round(high, 4),
        }

    return {"engine": engine_out, "baseline": baseline_out, "f1_difference": f1_difference}
