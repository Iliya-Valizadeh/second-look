"""Plain data classes for statements, the column mapping and flags.

Every class here is frozen and holds no behaviour beyond validating itself. Nothing
in this module opens a file, prints or reads the clock (ADR 0001). Money amounts use
`decimal.Decimal` so cents stay exact.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as Date
from decimal import Decimal
from enum import Enum
from typing import Literal

from .thresholds import Period

ColumnRef = str | int
"""A column, named by its header text or by its 0-based position when there is no
header (ADR 0003)."""

DATE_FORMATS = ("YYYY-MM-DD", "MM/DD/YYYY", "DD/MM/YYYY")


class SignConvention(Enum):
    """Which sign a signed amount column uses for money leaving the account."""

    CHARGES_NEGATIVE = "charges_negative"
    CHARGES_POSITIVE = "charges_positive"


@dataclass(frozen=True)
class ColumnMapping:
    """How to read one statement's CSV layout (ADR 0003).

    The amount is either one signed column plus a sign convention, or a separate
    debit and credit column. Give exactly one of those two shapes.
    """

    has_header: bool
    date_column: ColumnRef
    date_format: str
    description_columns: tuple[ColumnRef, ...]
    amount_column: ColumnRef | None = None
    sign_convention: SignConvention | None = None
    debit_column: ColumnRef | None = None
    credit_column: ColumnRef | None = None
    category_column: ColumnRef | None = None
    decimal_separator: str = "."

    def __post_init__(self) -> None:
        if self.date_format not in DATE_FORMATS:
            raise ValueError(f"date_format must be one of {DATE_FORMATS}")
        if not self.description_columns:
            raise ValueError("description_columns must not be empty")
        if self.decimal_separator not in (".", ","):
            raise ValueError("decimal_separator must be '.' or ','")
        has_signed = self.amount_column is not None
        has_split = self.debit_column is not None or self.credit_column is not None
        if has_signed and has_split:
            raise ValueError("give either amount_column or debit/credit columns, not both")
        if has_signed and self.sign_convention is None:
            raise ValueError("amount_column needs a sign_convention")
        if has_split and (self.debit_column is None or self.credit_column is None):
            raise ValueError("give both debit_column and credit_column")
        if not has_signed and not has_split:
            raise ValueError("give an amount_column, or a debit_column and credit_column")


@dataclass(frozen=True)
class Transaction:
    """One statement row, normalized so a charge is positive (ADR 0002).

    `line` is the 1-based line number in the CSV text the row came from. The header,
    when there is one, is line 1, so the first data row is line 2.
    """

    line: int
    date: Date
    description: str
    amount: Decimal
    category: str | None = None


@dataclass(frozen=True)
class SkippedRow:
    """One row the importer could not use, and why."""

    line: int
    reason: str


@dataclass(frozen=True)
class ImportSummary:
    """How many rows the importer read and used."""

    rows_read: int
    rows_used: int
    skipped: tuple[SkippedRow, ...]


@dataclass(frozen=True)
class ImportResult:
    """The transactions the importer built, plus a summary of what it skipped."""

    transactions: tuple[Transaction, ...]
    summary: ImportSummary


@dataclass(frozen=True)
class RecurringFlag:
    """A recurring charge, worth a second look for its yearly cost (ADR 0002)."""

    type: Literal["recurring"]
    lines: tuple[int, ...]
    merchant: str
    period: Period
    active: bool
    amount: Decimal
    count: int
    first_date: Date
    last_date: Date
    yearly_cost: Decimal | None
    reason: str


@dataclass(frozen=True)
class PriceIncreaseFlag:
    """A price rise on a recurring charge (ADR 0002)."""

    type: Literal["price_increase"]
    lines: tuple[int, ...]
    merchant: str
    period: Period
    old_amount: Decimal
    new_amount: Decimal
    reason: str
