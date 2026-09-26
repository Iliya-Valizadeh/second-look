"""Error analysis: which planted events each detector misses or flags wrongly, and why.

`python -m evaluation.error_analysis` (via `make error-analysis`) reruns the engine on
the same `200` test statements as `evaluation.evaluate`, matches its flags with the
same functions, and sorts every wrong flag and every miss into a cause. It writes
`reports/error_analysis.json`, which `reports/error_analysis.md` reads from.

This file only reads the engine. It changes no rule, threshold or seed. To explain an
unusual-charge miss it calls two private helpers in `second_look.unusual` (the typical
charge and the modified z-score), so the numbers it reports are the ones the engine
itself computed, not a second copy that could drift.
"""

from __future__ import annotations

import csv
import io
import json
import re
import statistics
from collections import Counter
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Any

from second_look.duplicate import detect_duplicates
from second_look.importer import parse_transactions
from second_look.merchant import merchant_key
from second_look.models import RecurringFlag, Transaction, UnusualFlag
from second_look.recurring import detect_recurring
from second_look.thresholds import (
    DUPLICATE_HABIT_DATES,
    DUPLICATE_WINDOW_DAYS,
    MIN_CATEGORY_HISTORY,
    MIN_MERCHANT_HISTORY,
    NEW_MERCHANT_MIN_DAYS,
    NEW_MERCHANT_RATIO,
    UNUSUAL_MIN_AMOUNT,
    UNUSUAL_MIN_RATIO,
    Z_THRESHOLD,
)
from second_look.unusual import _modified_z, _typical_charge, detect_unusual

from . import matching
from . import merchants as M
from .evaluate import TEST_SEED_FIRST, TEST_SEED_LAST, _round_floats
from .generator import generate_statement

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = REPO_ROOT / "reports" / "error_analysis.json"

# Every background merchant name, mapped to its generator category. A description
# contains exactly one of these names (the lists in merchants.py do not overlap).
_BACKGROUND_NAMES: dict[str, str] = {
    **{m.name: cat for cat, cfg in M.BACKGROUND_CATEGORIES.items() for m in cfg["merchants"]},
    M.TRANSIT.name: "transit",
}

# The four reason sentences in `second_look.unusual`, told apart by their wording.
_RULE_PATTERNS: dict[str, re.Pattern[str]] = {
    "merchant_score": re.compile(r"times your usual amount there"),
    "category_score": re.compile(r"times your usual amount for "),
    "new_merchant": re.compile(r"is your first charge at "),
    "very_large": re.compile(r"on \d{4}-\d{2}-\d{2} is [\d.]+ times your typical charge"),
}


def _background_category(description: str) -> str:
    for name, category in _BACKGROUND_NAMES.items():
        if name in description:
            return category
    return "other"


def _line_owners(answer_key: dict[str, Any]) -> dict[int, str]:
    """Map each line in a planted event or decoy to a short label of what it is."""
    owners: dict[int, str] = {}
    for e in answer_key["events"]:
        if e["type"] == "recurring":
            label = f"recurring:{e['kind']}"
            for line in e["lines"]:
                owners[line] = label
        elif e["type"] == "decoy":
            owners[e["line"]] = f"decoy:{e['kind']}"
        elif e["type"] == "duplicate":
            owners[e["lines"][1]] = "duplicate_copy"
        elif e["type"] == "unusual":
            owners[e["line"]] = f"unusual:{e['kind']}"
    return owners


def _what_is_line(line: int, owners: dict[int, str], by_line: dict[int, Transaction]) -> str:
    if line in owners:
        return owners[line]
    txn = by_line[line]
    if M.RENT_DESCRIPTION in txn.description:
        return "rent"
    return f"background:{_background_category(txn.description)}"


def _rules_fired(reason: str) -> str:
    fired = [name for name, pattern in _RULE_PATTERNS.items() if pattern.search(reason)]
    return "+".join(fired) if fired else "none"


def _ratio_band(ratio: float) -> str:
    lower = 0
    for upper in (2, 3, 5, 10):
        if ratio < upper:
            return f"{lower}x to {upper}x" if lower else f"under {upper}x"
        lower = upper
    return "10x or more"


def _analyse_recurring(
    flags: Sequence[RecurringFlag],
    answer_key: dict[str, Any],
    owners: dict[int, str],
    by_line: dict[int, Transaction],
    out: dict[str, Any],
) -> None:
    events = [e for e in answer_key["events"] if e["type"] == "recurring"]
    events_by_id = {e["id"]: e for e in events}
    flag_dicts = [{"lines": tuple(f.lines)} for f in flags]
    hits, matched_flags, matched_events = matching.match_recurring(flag_dicts, events)
    series_with_price_rise = {
        e["series"] for e in answer_key["events"] if e["type"] == "price_increase"
    }

    # The secondary check "right yearly cost" in metrics.json divides by every fixed
    # hit, stopped series included, and a stopped series has no yearly cost. This
    # splits that share into its parts.
    quality = out["hit_quality_detail"]
    for fi, eid in hits:
        e, f = events_by_id[eid], flags[fi]
        if e["kind"] != "fixed":
            continue
        quality["fixed_hits"] += 1
        if f.active != e["active"]:
            quality["wrong_active_status"] += 1
        elif not e["active"]:
            quality["stopped_right_status"] += 1
        elif str(f.yearly_cost) == e["expected_yearly_cost"]:
            quality["active_right_cost"] += 1
        else:
            quality["active_wrong_cost"] += 1

    for e in events:
        if e["kind"] != "fixed" or e["id"] in matched_events:
            continue
        if e.get("reference_word"):
            cause = "reference word in the description (ADR 0002 says these do not group)"
        else:
            cause = "other"
        out["misses_by_cause"][cause] += 1

    for fi, flag in enumerate(flags):
        if fi in matched_flags:
            continue
        kinds = Counter(_what_is_line(line, owners, by_line) for line in flag.lines)
        source = kinds.most_common(1)[0][0] if len(kinds) == 1 else "mixed"
        out["wrong_by_source"][source] += 1
        out["wrong_by_period"][flag.period] += 1
        group = "background" if source.startswith("background:") else source
        out["wrong_by_source_group_and_period"][f"{group}:{flag.period}"] += 1
        if source == "recurring:fixed":
            owner = next(
                e for e in events if e["kind"] == "fixed" and set(flag.lines) & set(e["lines"])
            )
            out["wrong_fixed_fragments"][
                "part of a series with a planted price increase"
                if owner["id"] in series_with_price_rise
                else "part of a series with no price increase"
            ] += 1
        out["wrong_by_active"]["active" if flag.active else "stopped"] += 1
        count_label = "6+" if flag.count >= 6 else str(flag.count)
        out["wrong_by_charge_count"][count_label] += 1
        if source.startswith("background:") and flag.period == "monthly":
            amounts = {by_line[line].amount for line in flag.lines}
            out["background_monthly_distinct_amounts"][
                "one amount" if len(amounts) == 1 else "several close amounts"
            ] += 1


def _analyse_price_increase(
    flags: Sequence[Any],
    recurring_flags: Sequence[RecurringFlag],
    answer_key: dict[str, Any],
    by_line: dict[int, Transaction],
    out: dict[str, Any],
) -> None:
    events = [e for e in answer_key["events"] if e["type"] == "price_increase"]
    series = {e["id"]: e for e in answer_key["events"] if e["type"] == "recurring"}
    decoy_lines = [
        e["line"]
        for e in answer_key["events"]
        if e["type"] == "decoy" and e["kind"] == "one_off_extra"
    ]
    flag_dicts = [{"lines": tuple(f.lines), "new_amount": f.new_amount} for f in flags]
    _, matched_flags, matched_events = matching.match_price_increase(flag_dicts, events)
    out["wrong_flags"] += len(flags) - len(matched_flags)

    for e in events:
        if e["id"] in matched_events:
            continue
        s = series[e["series"]]
        # The series' lines are sorted by line number. That is date order in chequing
        # files and reverse date order in credit card files (newest first).
        idx = s["lines"].index(e["first_new_line"])
        if answer_key["account_type"] == "chequing":
            after = s["lines"][idx:]
        else:
            after = s["lines"][: idx + 1]
        touching = [f for f in recurring_flags if e["first_new_line"] in f.lines]
        if touching and all(e["first_new_line"] in f.lines for f in touching):
            whole = any(len(set(f.lines) & set(s["lines"])) == len(s["lines"]) for f in touching)
        else:
            whole = False
        if not touching:
            cause = "new-price charges not in any recurring flag"
        elif whole:
            cause = "whole series found as one recurring flag, no price flag"
        else:
            cause = "series split into separate recurring flags"
        out["misses_by_cause"][cause] += 1
        # The engine only tries to join a series with the next amount group at that
        # merchant, in the order the groups first appear. A one-off extra charge (a
        # decoy) dated before the new price starts a group of its own in between.
        key = merchant_key(by_line[e["first_new_line"]].description)
        new_date = by_line[e["first_new_line"]].date
        extra_first = any(
            merchant_key(by_line[line].description) == key and by_line[line].date < new_date
            for line in decoy_lines
        )
        out["misses_with_one_off_extra_before_new_price"] += int(extra_first)
        out["misses_by_new_price_charges"][str(len(after))] += 1
        out["misses_by_period"][s["period"]] += 1
        if s.get("foreign_currency"):
            out["misses_foreign_currency"] += 1


def _analyse_duplicate(
    flags: Sequence[Any],
    transactions: Sequence[Transaction],
    answer_key: dict[str, Any],
    owners: dict[int, str],
    by_line: dict[int, Transaction],
    out: dict[str, Any],
) -> None:
    events = [e for e in answer_key["events"] if e["type"] == "duplicate"]
    flag_dicts = [{"lines": tuple(f.lines)} for f in flags]
    _, matched_flags, matched_events = matching.match_duplicate(flag_dicts, events)

    for fi, flag in enumerate(flags):
        if fi in matched_flags:
            continue
        kinds = sorted({_what_is_line(line, owners, by_line) for line in flag.lines})
        out["wrong_by_source"]["+".join(kinds)] += 1

    refunds = [t for t in transactions if t.amount < 0]
    for e in events:
        if e["refunded"] or e["id"] in matched_events:
            continue
        original, copy = by_line[e["lines"][0]], by_line[e["lines"][1]]
        key = merchant_key(copy.description)
        refunded = any(
            merchant_key(r.description) == key
            and -r.amount == copy.amount
            and 0 <= (r.date - min(original.date, copy.date)).days
            for r in refunds
        )
        dates = {
            t.date
            for t in transactions
            if t.amount == copy.amount and merchant_key(t.description) == key
        }
        if refunded:
            cause = "a refund of the same amount follows (the generator refunded a shopping charge)"
        elif len(dates) >= DUPLICATE_HABIT_DATES:
            cause = f"same amount on {DUPLICATE_HABIT_DATES} or more dates (habit test)"
        elif abs((copy.date - original.date).days) > DUPLICATE_WINDOW_DAYS:
            cause = "outside the window"
        else:
            cause = "other"
        out["misses_by_cause"][cause] += 1


def _unusual_context(
    transactions: Sequence[Transaction], recurring_flags: Sequence[RecurringFlag]
) -> dict[str, Any]:
    charges = [t for t in transactions if t.amount > 0]
    recurring_lines = {line for f in recurring_flags for line in f.lines}
    eligible = [t for t in charges if t.line not in recurring_lines]
    first_seen: dict[str, int] = {}
    for t in sorted(charges, key=lambda t: (t.date, t.line)):
        first_seen.setdefault(merchant_key(t.description), t.line)
    return {
        "charges": charges,
        "recurring_lines": recurring_lines,
        "eligible": eligible,
        "amount_counts": Counter(t.amount for t in charges),
        "first_seen": first_seen,
        "start": min(t.date for t in charges),
    }


def _merchant_history(
    txn: Transaction, key: str, eligible: Sequence[Transaction]
) -> list[Transaction]:
    return [t for t in eligible if merchant_key(t.description) == key and t.line != txn.line]


def _history_check(
    txn: Transaction, history: Sequence[Transaction], min_history: int
) -> tuple[str, float | None]:
    """Why the score test did or did not fire, and the ratio to the history median."""
    if len(history) < min_history:
        return "too little history", None
    z = _modified_z(txn.amount, history)
    median = statistics.median(t.amount for t in history)
    ratio = float(txn.amount / median)
    if z <= Z_THRESHOLD:
        return f"score at or below {Z_THRESHOLD}", ratio
    if txn.amount < median * UNUSUAL_MIN_RATIO:
        return f"under {UNUSUAL_MIN_RATIO}x the usual amount", ratio
    if txn.amount < UNUSUAL_MIN_AMOUNT:
        return f"under {UNUSUAL_MIN_AMOUNT} dollars", ratio
    return "fires", ratio


def _analyse_unusual(
    flags: Sequence[UnusualFlag],
    transactions: Sequence[Transaction],
    recurring_flags: Sequence[RecurringFlag],
    answer_key: dict[str, Any],
    owners: dict[int, str],
    by_line: dict[int, Transaction],
    out: dict[str, Any],
) -> None:
    events = [e for e in answer_key["events"] if e["type"] == "unusual"]
    flag_dicts = [{"lines": tuple(f.lines)} for f in flags]
    _, matched_flags, matched_events = matching.match_unusual(flag_dicts, events)
    ctx = _unusual_context(transactions, recurring_flags)

    for fi, flag in enumerate(flags):
        if fi in matched_flags:
            continue
        rules = _rules_fired(flag.reason)
        what = _what_is_line(flag.lines[0], owners, by_line)
        out["wrong_by_rule"][rules] += 1
        out["wrong_by_charge"][what] += 1
        out["wrong_by_account_type"][answer_key["account_type"]] += 1
        if rules == "merchant_score":
            txn = by_line[flag.lines[0]]
            key = merchant_key(txn.description)
            history = _merchant_history(txn, key, ctx["eligible"])
            _, ratio = _history_check(txn, history, MIN_MERCHANT_HISTORY)
            out["wrong_merchant_score_by_ratio"][_ratio_band(ratio or 0.0)] += 1
            out["wrong_merchant_score_by_history"][
                "5 to 9" if len(history) < 10 else ("10 to 19" if len(history) < 20 else "20+")
            ] += 1
        if rules == "category_score":
            out["wrong_category_score_by_charge"][what] += 1
        if rules == "new_merchant":
            out["wrong_new_merchant_by_charge"][what] += 1

    for fi in matched_flags:
        out["hits_by_rule"][_rules_fired(flags[fi].reason)] += 1

    # How many charges the per-merchant score was computed for at all (enough history),
    # so its wrong flags can be read as a share of the charges it looked at.
    per_key = Counter(merchant_key(t.description) for t in ctx["eligible"])
    out["charges_scored_per_merchant"] += sum(
        1
        for t in ctx["eligible"]
        if per_key[merchant_key(t.description)] - 1 >= MIN_MERCHANT_HISTORY
    )
    out["charges_eligible"] += len(ctx["eligible"])

    for e in events:
        kind = e["kind"]
        out["events_by_kind"][kind] += 1
        out["events_by_kind_and_account"][f"{kind}:{answer_key['account_type']}"] += 1
        if e["id"] in matched_events:
            out["hits_by_kind_and_account"][f"{kind}:{answer_key['account_type']}"] += 1
            if kind == "spike_known_merchant":
                out["spike_hits_by_factor"][_ratio_band(e["factor"])] += 1
            continue
        out["misses_by_kind"][kind] += 1
        txn = by_line[e["line"]]
        if txn.line in ctx["recurring_lines"]:
            out["misses_by_cause"][f"{kind}: absorbed into a recurring flag"] += 1
            continue
        key = merchant_key(txn.description)
        if kind == "spike_known_merchant":
            out["spike_misses_by_factor"][_ratio_band(e["factor"])] += 1
            history = _merchant_history(txn, key, ctx["eligible"])
            merchant_cause, _ = _history_check(txn, history, MIN_MERCHANT_HISTORY)
            if txn.category is None:
                category_cause = "no category column"
            else:
                cat_history = [
                    t for t in ctx["eligible"] if t.category == txn.category and t.line != txn.line
                ]
                category_cause, _ = _history_check(txn, cat_history, MIN_CATEGORY_HISTORY)
            out["misses_by_cause"][
                f"{kind}: merchant test {merchant_cause}; category test {category_cause}"
            ] += 1
            category = _background_category(txn.description)
            out["spike_misses_by_category"][category] += 1
        else:
            typical = _typical_charge(ctx["amount_counts"], txn.amount)
            days = (txn.date - ctx["start"]).days
            if ctx["first_seen"][key] != txn.line:
                cause = "not the first charge at that merchant"
            elif days < NEW_MERCHANT_MIN_DAYS:
                cause = f"under {NEW_MERCHANT_MIN_DAYS} days of history before it"
            elif txn.amount < typical * NEW_MERCHANT_RATIO:
                cause = f"under {NEW_MERCHANT_RATIO}x the typical charge"
                out["new_merchant_miss_ratio_to_typical"].append(float(txn.amount / typical))
            else:
                cause = "other"
            out["misses_by_cause"][f"{kind}: {cause}"] += 1


def _new_section(
    *counters: str, lists: Sequence[str] = (), ints: Sequence[str] = ()
) -> dict[str, Any]:
    section: dict[str, Any] = {name: Counter() for name in counters}
    section.update({name: [] for name in lists})
    section.update({name: 0 for name in ints})
    return section


def run(seeds: range = range(TEST_SEED_FIRST, TEST_SEED_LAST + 1)) -> dict[str, Any]:
    """Sort every wrong flag and miss on `seeds` (the test seeds by default) into causes."""
    out: dict[str, Any] = {
        "recurring": _new_section(
            "misses_by_cause",
            "wrong_by_source",
            "wrong_by_period",
            "wrong_by_active",
            "wrong_by_charge_count",
            "wrong_by_source_group_and_period",
            "wrong_fixed_fragments",
            "background_monthly_distinct_amounts",
            "hit_quality_detail",
        ),
        "price_increase": _new_section(
            "misses_by_cause",
            "misses_by_new_price_charges",
            "misses_by_period",
            ints=(
                "wrong_flags",
                "misses_foreign_currency",
                "misses_with_one_off_extra_before_new_price",
            ),
        ),
        "duplicate": _new_section("misses_by_cause", "wrong_by_source"),
        "unusual": _new_section(
            "wrong_by_rule",
            "wrong_by_charge",
            "wrong_by_account_type",
            "wrong_merchant_score_by_ratio",
            "wrong_merchant_score_by_history",
            "wrong_category_score_by_charge",
            "wrong_new_merchant_by_charge",
            "hits_by_rule",
            "events_by_kind",
            "events_by_kind_and_account",
            "hits_by_kind_and_account",
            "misses_by_kind",
            "misses_by_cause",
            "spike_hits_by_factor",
            "spike_misses_by_factor",
            "spike_misses_by_category",
            lists=("new_merchant_miss_ratio_to_typical",),
            ints=("charges_scored_per_merchant", "charges_eligible"),
        ),
    }

    for seed in seeds:
        csv_text, mapping, answer_key = generate_statement(seed, stress=False)
        rows = list(csv.reader(io.StringIO(csv_text)))
        transactions = parse_transactions(rows, mapping).transactions
        statement_end = max((t.date for t in transactions), default=date(2023, 1, 1))
        by_line = {t.line: t for t in transactions}
        owners = _line_owners(answer_key)

        recurring_flags, price_flags = detect_recurring(transactions, statement_end)
        duplicate_flags = detect_duplicates(transactions, recurring_flags)
        unusual_flags = detect_unusual(transactions, recurring_flags)

        _analyse_recurring(recurring_flags, answer_key, owners, by_line, out["recurring"])
        _analyse_price_increase(
            price_flags, recurring_flags, answer_key, by_line, out["price_increase"]
        )
        _analyse_duplicate(
            duplicate_flags, transactions, answer_key, owners, by_line, out["duplicate"]
        )
        _analyse_unusual(
            unusual_flags,
            transactions,
            recurring_flags,
            answer_key,
            owners,
            by_line,
            out["unusual"],
        )

    u = out["unusual"]
    merchant_wrong = sum(n for rules, n in u["wrong_by_rule"].items() if "merchant_score" in rules)
    u["derived"] = {
        "wrong_flags_with_merchant_score": merchant_wrong,
        "merchant_score_wrong_share_of_scored_charges": merchant_wrong
        / u["charges_scored_per_merchant"],
        "charges_scored_per_merchant_per_statement": u["charges_scored_per_merchant"] / len(seeds),
        "spike_recall_by_factor": {
            band: u["spike_hits_by_factor"].get(band, 0)
            / (u["spike_hits_by_factor"].get(band, 0) + u["spike_misses_by_factor"].get(band, 0))
            for band in sorted(set(u["spike_hits_by_factor"]) | set(u["spike_misses_by_factor"]))
        },
        "spike_recall_by_account": {
            acct: u["hits_by_kind_and_account"].get(f"spike_known_merchant:{acct}", 0)
            / u["events_by_kind_and_account"][f"spike_known_merchant:{acct}"]
            for acct in ("chequing", "credit")
        },
    }

    new_price_counts = [int(n) for n in out["price_increase"]["misses_by_new_price_charges"]]
    out["price_increase"]["misses_new_price_charges_range"] = {
        "min": min(new_price_counts, default=0),
        "max": max(new_price_counts, default=0),
    }

    ratios = sorted(out["unusual"].pop("new_merchant_miss_ratio_to_typical"))
    out["unusual"]["new_merchant_miss_ratio_to_typical"] = {
        "count": len(ratios),
        "max": round(max(ratios), 4) if ratios else None,
        "median": round(statistics.median(ratios), 4) if ratios else None,
    }
    for section in out.values():
        for name, value in list(section.items()):
            if isinstance(value, Counter):
                section[name] = dict(sorted(value.items()))
    out["test_seeds"] = {
        "first": seeds[0],
        "last": seeds[-1],
        "statements": len(seeds),
    }
    return out


def write(result: dict[str, Any]) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(_round_floats(result), indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    result = run()
    write(result)
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
