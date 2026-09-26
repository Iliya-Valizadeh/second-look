"""Turn already-split CSV rows into normalized transactions (ADR 0003).

`parse_transactions` takes the whole file as rows the caller already split (for
example with `csv.reader`), plus a `ColumnMapping` that says which column holds
what. It does no file or network I/O and never guesses a bank's layout: the caller
always gives the mapping. Splitting raw CSV text into rows, sniffing the delimiter
and decoding bytes are a door's job (ADR 0001); this module only maps and normalizes
rows it is handed.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import date
from decimal import Decimal, InvalidOperation

from .models import (
    ColumnMapping,
    ColumnRef,
    ImportResult,
    ImportSummary,
    SignConvention,
    SkippedRow,
    Transaction,
)

RawRow = Sequence[str]

_STRIP_RE = re.compile(r"[^0-9.\-]")

# Which parts of each split date string are the year, month and day, by position.
_DATE_FIELD_ORDER: dict[str, tuple[int, int, int]] = {
    "YYYY-MM-DD": (0, 1, 2),
    "MM/DD/YYYY": (2, 0, 1),
    "DD/MM/YYYY": (2, 1, 0),
}


def parse_transactions(rows: Sequence[RawRow], mapping: ColumnMapping) -> ImportResult:
    """Map `rows` through `mapping` into normalized transactions.

    `rows` holds every row of the file in order, including the header row when
    `mapping.has_header` is true. Line numbers in the result are 1-based and count
    from the start of `rows`, so the header (when present) is line 1 and the first
    data row is line 2.
    """
    header_row = rows[0] if mapping.has_header and rows else None
    header_index = (
        {name: idx for idx, name in enumerate(header_row)} if header_row is not None else None
    )
    data_start = 1 if header_row is not None else 0

    def column_index(ref: ColumnRef) -> int:
        if isinstance(ref, int):
            return ref
        if header_index is None:
            raise ValueError(f"column {ref!r} needs a header row")
        if ref not in header_index:
            raise ValueError(f"no column named {ref!r} in the header row")
        return header_index[ref]

    date_idx = column_index(mapping.date_column)
    description_idxs = [column_index(column) for column in mapping.description_columns]
    category_idx = (
        column_index(mapping.category_column) if mapping.category_column is not None else None
    )
    amount_idx = column_index(mapping.amount_column) if mapping.amount_column is not None else None
    debit_idx = column_index(mapping.debit_column) if mapping.debit_column is not None else None
    credit_idx = column_index(mapping.credit_column) if mapping.credit_column is not None else None

    transactions: list[Transaction] = []
    skipped: list[SkippedRow] = []

    for offset, row in enumerate(rows[data_start:]):
        line = data_start + offset + 1
        if _is_blank(row):
            skipped.append(SkippedRow(line, "blank row"))
            continue
        if header_row is not None and tuple(row) == tuple(header_row):
            skipped.append(SkippedRow(line, "repeated header row"))
            continue
        try:
            txn_date = _parse_date(row[date_idx], mapping.date_format)
            description = " ".join(row[i].strip() for i in description_idxs).strip()
            amount = _parse_row_amount(row, mapping, amount_idx, debit_idx, credit_idx)
            category = (row[category_idx].strip() or None) if category_idx is not None else None
        except (ValueError, IndexError, InvalidOperation) as exc:
            skipped.append(SkippedRow(line, str(exc)))
            continue
        transactions.append(
            Transaction(
                line=line, date=txn_date, description=description, amount=amount, category=category
            )
        )

    return ImportResult(
        transactions=tuple(transactions),
        summary=ImportSummary(
            rows_read=len(rows), rows_used=len(transactions), skipped=tuple(skipped)
        ),
    )


def _is_blank(row: RawRow) -> bool:
    return all(not cell.strip() for cell in row)


def _parse_date(raw: str, date_format: str) -> date:
    separator = "-" if date_format == "YYYY-MM-DD" else "/"
    parts = raw.strip().split(separator)
    if len(parts) != 3:
        raise ValueError(f"cannot read {raw!r} as a {date_format} date")
    try:
        numbers = [int(part) for part in parts]
    except ValueError as exc:
        raise ValueError(f"cannot read {raw!r} as a {date_format} date") from exc
    year_pos, month_pos, day_pos = _DATE_FIELD_ORDER[date_format]
    return date(numbers[year_pos], numbers[month_pos], numbers[day_pos])


def _parse_amount(raw: str, decimal_separator: str) -> Decimal:
    text = raw.strip()
    if not text:
        raise ValueError("empty amount")

    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative = True
        text = text[1:-1]
    if text.endswith("-"):
        negative = True
        text = text[:-1]
    text = text.strip()
    if text.startswith("-"):
        negative = True
        text = text[1:]

    if decimal_separator == ",":
        text = text.replace(".", "").replace(",", ".")
    else:
        text = text.replace(",", "")
    text = _STRIP_RE.sub("", text)
    if not text or text == "-":
        raise ValueError(f"cannot read {raw!r} as an amount")

    try:
        value = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"cannot read {raw!r} as an amount") from exc
    return -value if negative else value


def _parse_row_amount(
    row: RawRow,
    mapping: ColumnMapping,
    amount_idx: int | None,
    debit_idx: int | None,
    credit_idx: int | None,
) -> Decimal:
    if amount_idx is not None:
        value = _parse_amount(row[amount_idx], mapping.decimal_separator)
        if mapping.sign_convention is SignConvention.CHARGES_NEGATIVE:
            return -value
        return value

    debit_raw = row[debit_idx].strip() if debit_idx is not None else ""
    credit_raw = row[credit_idx].strip() if credit_idx is not None else ""
    has_debit, has_credit = bool(debit_raw), bool(credit_raw)
    if has_debit and has_credit:
        raise ValueError("row has both a debit and a credit amount")
    if has_debit:
        return _parse_amount(debit_raw, mapping.decimal_separator)
    if has_credit:
        return -_parse_amount(credit_raw, mapping.decimal_separator)
    raise ValueError("row has no debit or credit amount")
