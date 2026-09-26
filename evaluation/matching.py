"""Match a detector's flags to the planted events in one statement's answer key
(docs/eval_plan.md, "Matching a flag to a planted event").

Every function here takes flags and events for one statement and one flag type, and
returns `(hits, matched_flag_indexes, matched_event_ids)`. `hits` is a list of
`(flag_index, event_id)` pairs. Matching is one-to-one: a flag or event that appears
in one pair cannot appear in another. Flags are plain dicts with a `lines` tuple (and
`new_amount` for price increases), so the same functions score the engine and the
baselines.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from .common import is_close_amount

Hit = tuple[int, str]


def match_recurring(
    flags: list[dict[str, Any]], events: list[dict[str, Any]]
) -> tuple[list[Hit], set[int], set[str]]:
    candidates = []
    for fi, flag in enumerate(flags):
        flag_lines = set(flag["lines"])
        for event in events:
            event_lines = set(event["lines"])
            shared = len(flag_lines & event_lines)
            if shared == 0:
                continue
            if 2 * shared >= len(flag_lines) and 2 * shared >= len(event_lines):
                candidates.append((shared, event["id"], fi))
    candidates.sort(key=lambda c: (-c[0], c[1], c[2]))
    return _take_greedy(candidates)


def match_price_increase(
    flags: list[dict[str, Any]], events: list[dict[str, Any]]
) -> tuple[list[Hit], set[int], set[str]]:
    candidates = []
    for fi, flag in enumerate(flags):
        flag_lines = set(flag["lines"])
        for event in events:
            if event["first_new_line"] not in flag_lines:
                continue
            if not is_close_amount(flag["new_amount"], Decimal(event["new_amount"])):
                continue
            candidates.append((1, event["id"], fi))
    candidates.sort(key=lambda c: (-c[0], c[1], c[2]))
    return _take_greedy(candidates)


def match_duplicate(
    flags: list[dict[str, Any]], events: list[dict[str, Any]]
) -> tuple[list[Hit], set[int], set[str]]:
    events_by_lines: dict[frozenset[int], str] = {}
    for event in events:
        if event["refunded"]:
            continue
        events_by_lines[frozenset(event["lines"])] = event["id"]

    matched_flags: set[int] = set()
    matched_events: set[str] = set()
    hits: list[Hit] = []
    for fi, flag in enumerate(flags):
        key = frozenset(flag["lines"])
        event_id = events_by_lines.get(key)
        if event_id is None or event_id in matched_events:
            continue
        matched_flags.add(fi)
        matched_events.add(event_id)
        hits.append((fi, event_id))
    return hits, matched_flags, matched_events


def match_unusual(
    flags: list[dict[str, Any]], events: list[dict[str, Any]]
) -> tuple[list[Hit], set[int], set[str]]:
    events_by_line = {event["line"]: event["id"] for event in events}
    matched_flags: set[int] = set()
    matched_events: set[str] = set()
    hits: list[Hit] = []
    for fi, flag in enumerate(flags):
        line = flag["lines"][0]
        event_id = events_by_line.get(line)
        if event_id is None or event_id in matched_events:
            continue
        matched_flags.add(fi)
        matched_events.add(event_id)
        hits.append((fi, event_id))
    return hits, matched_flags, matched_events


def _take_greedy(candidates: list[tuple[int, str, int]]) -> tuple[list[Hit], set[int], set[str]]:
    matched_flags: set[int] = set()
    matched_events: set[str] = set()
    hits: list[Hit] = []
    for cand in candidates:
        _, event_id, fi = cand
        if fi in matched_flags or event_id in matched_events:
            continue
        matched_flags.add(fi)
        matched_events.add(event_id)
        hits.append((fi, event_id))
    return hits, matched_flags, matched_events
