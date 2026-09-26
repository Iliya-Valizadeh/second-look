"""Every number the detection rules use, named and in one place (ADR 0002).

The reasons for each number are in
`docs/decisions/0002-detection-rules-and-thresholds.md`. This module only holds the
constants, so the code, that record and `docs/reference.md` can be checked against
each other. Some constants (the duplicate and unusual-transaction ones) are not read
by any code yet; they are here because ADR 0002 fixes every number before any of the
detectors that use it are written.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

Period = Literal["weekly", "monthly", "yearly"]

# --- Merchant amount grouping -----------------------------------------------------

SAME_AMOUNT_ABS = Decimal("0.05")
"""Two charges count as the same amount when they differ by no more than the larger
of this, in dollars, and `SAME_AMOUNT_REL` of the smaller amount."""

SAME_AMOUNT_REL = Decimal("0.03")
"""The relative half of the same-amount tolerance (three percent)."""


@dataclass(frozen=True)
class PeriodRule:
    """One row of the period table (weekly, monthly or yearly)."""

    name: Period
    gap_low_days: int
    gap_high_days: int
    min_charges: int
    period_days: int
    charges_per_year: int
    price_rise_min_new: int
    allow_one_skip: bool
    """Whether one gap of about two periods (a skipped charge) is still allowed."""


PERIOD_RULES: tuple[PeriodRule, ...] = (
    PeriodRule(
        name="weekly",
        gap_low_days=6,
        gap_high_days=8,
        min_charges=4,
        period_days=7,
        charges_per_year=52,
        price_rise_min_new=2,
        allow_one_skip=True,
    ),
    PeriodRule(
        name="monthly",
        gap_low_days=25,
        gap_high_days=35,
        min_charges=3,
        period_days=30,
        charges_per_year=12,
        price_rise_min_new=2,
        allow_one_skip=True,
    ),
    PeriodRule(
        name="yearly",
        gap_low_days=358,
        gap_high_days=372,
        min_charges=2,
        period_days=365,
        charges_per_year=1,
        price_rise_min_new=1,
        allow_one_skip=False,
    ),
)

ACTIVE_MAX_PERIODS = Decimal("1.5")
"""A series is active when its last charge is no more than this many periods before
the statement end."""

# --- Price increases --------------------------------------------------------------
# `PeriodRule.price_rise_min_new` above holds the per-period minimum new-price count.

# --- Duplicate charges (not read by any code yet; see the module docstring) -------

DUPLICATE_WINDOW_DAYS = 2
REFUND_LOOKAHEAD_DAYS = 14
DUPLICATE_HABIT_PAIRS = 3

# --- Unusual transactions (not read by any code yet; see the module docstring) ----

MIN_STATEMENT_DAYS = 60
MIN_STATEMENT_CHARGES = 30
Z_THRESHOLD = 3.5
MIN_LOG_SCALE = 0.1
MIN_MERCHANT_HISTORY = 5
MIN_CATEGORY_HISTORY = 10
UNUSUAL_MIN_RATIO = 2
UNUSUAL_MIN_AMOUNT = Decimal("25")
NEW_MERCHANT_MIN_DAYS = 60
NEW_MERCHANT_RATIO = 3
LARGE_CHARGE_RATIO = 10
