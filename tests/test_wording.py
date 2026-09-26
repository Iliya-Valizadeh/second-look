"""The wording guard from ADR 0005.

This test runs every detector on synthetic statements built to trigger each of the
nine reason patterns in ADR 0002 (three recurring, one price increase, one
duplicate, and four unusual-transaction reasons), then checks every reason string,
the CLI's section title and its "not financial advice" footer for the one word this
tool never uses, and the handful of other words ADR 0005 also bans.

Following ADR 0005's own convention, the banned word is built from parts here, so the
plain word appears nowhere in this repo outside this comment about it.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from second_look import cli
from second_look.duplicate import detect_duplicates
from second_look.models import Transaction
from second_look.recurring import detect_recurring
from second_look.unusual import detect_unusual

START = date(2024, 1, 1)

BANNED_WORDS = (
    "fr" + "aud",
    "suspicious",
    "scam",
    "stolen",
    "criminal",
    "alert",
    "warning",
)


def d(offset: int) -> date:
    return START + timedelta(days=offset)


def txn(
    line: int,
    offset: int,
    amount: str,
    description: str = "FILLER STORE",
    category: str | None = None,
) -> Transaction:
    return Transaction(
        line=line,
        date=d(offset),
        description=description,
        amount=Decimal(amount),
        category=category,
    )


def _all_reasons() -> list[str]:
    reasons: list[str] = []

    # Recurring: active monthly, stopped, and the "twice, a year apart" wording.
    monthly = [txn(2, 0, "9.99"), txn(3, 30, "9.99"), txn(4, 60, "9.99")]
    recurring, _ = detect_recurring(monthly, statement_end=d(65))
    reasons += [f.reason for f in recurring]

    stopped = [txn(2, 0, "9.99"), txn(3, 30, "9.99"), txn(4, 60, "9.99")]
    recurring, _ = detect_recurring(stopped, statement_end=d(400))
    reasons += [f.reason for f in recurring]

    yearly_twice = [txn(2, 0, "59.99"), txn(3, 365, "59.99")]
    recurring, _ = detect_recurring(yearly_twice, statement_end=d(370))
    reasons += [f.reason for f in recurring]

    # Price increase.
    price_rise = [
        txn(2, 0, "9.99"),
        txn(3, 30, "9.99"),
        txn(4, 60, "9.99"),
        txn(5, 90, "11.99"),
        txn(6, 120, "11.99"),
    ]
    recurring, price = detect_recurring(price_rise, statement_end=d(125))
    reasons += [f.reason for f in recurring] + [f.reason for f in price]

    # Duplicate.
    duplicate_pair = [txn(2, 0, "4.50"), txn(3, 1, "4.50")]
    reasons += [f.reason for f in detect_duplicates(duplicate_pair, recurring_flags=[])]

    # Unusual: per-merchant, per-category, new merchant, very large.
    merchant_filler = [txn(2 + i, i * 3, "10.00") for i in range(29)]
    merchant_outlier = txn(31, 10, "40.00")
    reasons += [
        f.reason for f in detect_unusual([*merchant_filler, merchant_outlier], recurring_flags=[])
    ]

    groc_a = [txn(2 + i, i * 5, "8.00", "GROC A", category="GROCERY") for i in range(15)]
    groc_b = [txn(17 + i, i * 5, "8.00", "GROC B", category="GROCERY") for i in range(15)]
    category_outlier = txn(32, 20, "60.00", "GROC C", category="GROCERY")
    reasons += [
        f.reason for f in detect_unusual([*groc_a, *groc_b, category_outlier], recurring_flags=[])
    ]

    new_merchant_filler = [txn(2 + i, i * 3, "10.00") for i in range(30)]
    new_merchant_outlier = txn(32, 65, "45.00", "NEW GADGET STORE")
    reasons += [
        f.reason
        for f in detect_unusual([*new_merchant_filler, new_merchant_outlier], recurring_flags=[])
    ]

    large_filler = [txn(2 + i, i * 3, "10.00") for i in range(28)]
    large_established = [txn(30, 5, "10.00", "LARGE MART"), txn(31, 40, "10.00", "LARGE MART")]
    large_outlier = txn(32, 70, "150.00", "LARGE MART")
    reasons += [
        f.reason
        for f in detect_unusual(
            [*large_filler, *large_established, large_outlier], recurring_flags=[]
        )
    ]

    return reasons


def test_every_reason_pattern_fires_at_least_once() -> None:
    # Guards the test itself: if a scenario stops firing, this test would otherwise
    # pass on an empty list and check nothing.
    assert len(_all_reasons()) >= 9


def test_no_reason_string_uses_a_banned_word() -> None:
    for reason in _all_reasons():
        lowered = reason.lower()
        for banned in BANNED_WORDS:
            assert banned not in lowered, f"{banned!r} appears in reason: {reason!r}"


def test_the_cli_titles_and_footer_use_no_banned_word() -> None:
    for text in (cli.SECTION_TITLE, cli.NOT_ADVICE_FOOTER):
        lowered = text.lower()
        for banned in BANNED_WORDS:
            assert banned not in lowered, f"{banned!r} appears in: {text!r}"
