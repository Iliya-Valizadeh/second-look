"""Door 1: the `second-look` command line (ADR 0001).

This is the one module in the package that reads a file, prints text or touches
`sys.argv`. It reads the statement's bytes, decodes them, splits them into rows, and
hands them to the core (`importer`, `recurring`, `duplicate`, `unusual`). The core
never sees a file path. Nothing here makes a network call or reads any key.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from collections.abc import Sequence
from dataclasses import fields, is_dataclass
from datetime import date as Date
from decimal import Decimal
from pathlib import Path

from .duplicate import detect_duplicates
from .importer import parse_transactions
from .models import ColumnMapping, ColumnRef, Flag, ImportSummary, SignConvention
from .recurring import detect_recurring
from .unusual import detect_unusual

SECTION_TITLE = "Worth a second look"

NOT_ADVICE_FOOTER = (
    "This tool points out charges you may want to look at again. It is not financial "
    "advice. It cannot tell whether a charge is right or wrong. Only you, the "
    "merchant or your bank can."
)

_FALLBACK_ENCODING = "cp1252"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="second-look",
        description="Find recurring charges, price rises, duplicates and odd spending",
    )
    parser.add_argument("statement", help="path to the statement CSV file")
    parser.add_argument(
        "--json", action="store_true", help="print the flags as JSON instead of plain text"
    )
    parser.add_argument(
        "--no-header",
        action="store_true",
        help="the file has no header row (columns are given by position, starting at 0)",
    )
    parser.add_argument("--date-column", default="Date", help="the date column (default: Date)")
    parser.add_argument(
        "--date-format",
        default="YYYY-MM-DD",
        choices=("YYYY-MM-DD", "MM/DD/YYYY", "DD/MM/YYYY"),
        help="the date format (default: YYYY-MM-DD)",
    )
    parser.add_argument(
        "--description-column",
        action="append",
        dest="description_columns",
        help="a description column; give it more than once to join several columns",
    )
    parser.add_argument("--category-column", default=None, help="an optional category column")
    parser.add_argument(
        "--amount-column",
        default=None,
        help="a single signed amount column (needs --sign-convention)",
    )
    parser.add_argument(
        "--sign-convention",
        choices=("charges-negative", "charges-positive"),
        default=None,
        help="which sign the amount column uses for money leaving the account",
    )
    parser.add_argument(
        "--debit-column", default=None, help="a debit column (use with --credit-column)"
    )
    parser.add_argument(
        "--credit-column", default=None, help="a credit column (use with --debit-column)"
    )
    parser.add_argument(
        "--decimal-separator",
        default=".",
        choices=(".", ","),
        help="the decimal separator (default: .)",
    )
    parser.add_argument(
        "--delimiter", default=None, help="the CSV delimiter; sniffed from the file when not given"
    )
    return parser


def _column_ref(value: str) -> ColumnRef:
    return int(value) if value.isdigit() else value


def _sign_convention(value: str | None) -> SignConvention | None:
    if value is None:
        return None
    return {
        "charges-negative": SignConvention.CHARGES_NEGATIVE,
        "charges-positive": SignConvention.CHARGES_POSITIVE,
    }[value]


def build_column_mapping(args: argparse.Namespace) -> ColumnMapping:
    description_columns = args.description_columns or ["Description"]
    return ColumnMapping(
        has_header=not args.no_header,
        date_column=_column_ref(args.date_column),
        date_format=args.date_format,
        description_columns=tuple(_column_ref(c) for c in description_columns),
        amount_column=_column_ref(args.amount_column) if args.amount_column is not None else None,
        sign_convention=_sign_convention(args.sign_convention),
        debit_column=_column_ref(args.debit_column) if args.debit_column is not None else None,
        credit_column=_column_ref(args.credit_column) if args.credit_column is not None else None,
        category_column=_column_ref(args.category_column)
        if args.category_column is not None
        else None,
        decimal_separator=args.decimal_separator,
    )


def decode_statement(raw: bytes) -> str:
    """Decode a statement's raw bytes as UTF-8, or Windows-1252 if that fails (ADR 0003)."""
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode(_FALLBACK_ENCODING)


def split_rows(text: str, delimiter: str | None) -> list[list[str]]:
    """Split statement text into rows, sniffing the delimiter when none is given (ADR 0003)."""
    if delimiter is None:
        sample = "\n".join(text.splitlines()[:5])
        try:
            delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t").delimiter
        except csv.Error:
            delimiter = ","
    return list(csv.reader(io.StringIO(text), delimiter=delimiter))


def run(rows: Sequence[Sequence[str]], mapping: ColumnMapping) -> tuple[list[Flag], ImportSummary]:
    """Run every detector on `rows` and return the flags and the import summary."""
    result = parse_transactions(rows, mapping)
    # An empty statement has no "last date"; the fallback is never used for anything,
    # since every detector returns nothing when there are no transactions.
    statement_end = max((t.date for t in result.transactions), default=Date(1970, 1, 1))
    recurring_flags, price_flags = detect_recurring(result.transactions, statement_end)
    duplicate_flags = detect_duplicates(result.transactions, recurring_flags)
    unusual_flags = detect_unusual(result.transactions, recurring_flags)
    flags: list[Flag] = [*recurring_flags, *price_flags, *duplicate_flags, *unusual_flags]
    return flags, result.summary


def _to_jsonable(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: _to_jsonable(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Date):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(v) for v in value]
    return value


def format_json(flags: Sequence[Flag], summary: ImportSummary) -> str:
    payload = {
        "title": SECTION_TITLE,
        "summary": _to_jsonable(summary),
        "flags": [_to_jsonable(flag) for flag in flags],
        "not_financial_advice": NOT_ADVICE_FOOTER,
    }
    return json.dumps(payload, indent=2)


def format_text(flags: Sequence[Flag], summary: ImportSummary) -> str:
    lines = [SECTION_TITLE, "=" * len(SECTION_TITLE), ""]
    if not flags:
        lines.append("Nothing worth a second look in this statement.")
    for flag in flags:
        line_ref = ", ".join(str(n) for n in flag.lines)
        lines.append(f"- (line {line_ref}) {flag.reason}")
    lines.append("")
    lines.append(
        f"Read {summary.rows_read} rows, used {summary.rows_used}, skipped {len(summary.skipped)}."
    )
    for row in summary.skipped:
        lines.append(f"  line {row.line}: {row.reason}")
    lines.append("")
    lines.append(NOT_ADVICE_FOOTER)
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    try:
        mapping = build_column_mapping(args)
    except ValueError as exc:
        print(f"second-look: {exc}", file=sys.stderr)
        return 2

    path = Path(args.statement)
    try:
        raw = path.read_bytes()
    except OSError as exc:
        print(f"second-look: cannot read {args.statement}: {exc}", file=sys.stderr)
        return 2

    text = decode_statement(raw)
    rows = split_rows(text, args.delimiter)

    try:
        flags, summary = run(rows, mapping)
    except ValueError as exc:
        print(f"second-look: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(format_json(flags, summary))
    else:
        print(format_text(flags, summary))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
