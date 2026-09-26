"""Tests for the generic CSV importer (ADR 0003), on small hand-built rows.

`rows` throughout is what a door would hand the core after splitting CSV text into
fields, for example with `csv.reader`. No file is opened here.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from second_look.importer import parse_transactions
from second_look.models import ColumnMapping, SignConvention


def _chequing_mapping(**overrides: object) -> ColumnMapping:
    base: dict[str, object] = {
        "has_header": True,
        "date_column": "Date",
        "date_format": "YYYY-MM-DD",
        "description_columns": ("Description",),
        "amount_column": "Amount",
        "sign_convention": SignConvention.CHARGES_NEGATIVE,
        "category_column": None,
    }
    base.update(overrides)
    return ColumnMapping(**base)  # type: ignore[arg-type]


def test_a_signed_column_with_charges_negative_is_flipped_to_charges_positive() -> None:
    rows = [
        ["Date", "Description", "Amount"],
        ["2024-01-05", "COFFEE SHOP", "-4.50"],
        ["2024-01-06", "PAYROLL", "2000.00"],
    ]
    result = parse_transactions(rows, _chequing_mapping())
    assert [t.amount for t in result.transactions] == [Decimal("4.50"), Decimal("-2000.00")]


def test_a_signed_column_with_charges_positive_is_kept_as_is() -> None:
    rows = [
        ["Date", "Description", "Amount"],
        ["2024-01-05", "COFFEE SHOP", "4.50"],
    ]
    mapping = _chequing_mapping(sign_convention=SignConvention.CHARGES_POSITIVE)
    result = parse_transactions(rows, mapping)
    assert result.transactions[0].amount == Decimal("4.50")


def test_separate_debit_and_credit_columns() -> None:
    rows = [
        ["Transaction Date", "Description", "Debit", "Credit"],
        ["01/05/2024", "COFFEE SHOP", "4.50", ""],
        ["01/06/2024", "REFUND", "", "10.00"],
    ]
    mapping = ColumnMapping(
        has_header=True,
        date_column="Transaction Date",
        date_format="MM/DD/YYYY",
        description_columns=("Description",),
        debit_column="Debit",
        credit_column="Credit",
    )
    result = parse_transactions(rows, mapping)
    assert [t.amount for t in result.transactions] == [Decimal("4.50"), Decimal("-10.00")]


def test_a_row_with_both_debit_and_credit_is_skipped() -> None:
    rows = [
        ["Date", "Description", "Debit", "Credit"],
        ["2024-01-05", "ODD ROW", "4.50", "1.00"],
    ]
    mapping = ColumnMapping(
        has_header=True,
        date_column="Date",
        date_format="YYYY-MM-DD",
        description_columns=("Description",),
        debit_column="Debit",
        credit_column="Credit",
    )
    result = parse_transactions(rows, mapping)
    assert result.transactions == ()
    assert result.summary.skipped[0].line == 2
    assert "both a debit and a credit" in result.summary.skipped[0].reason


def test_multiple_description_columns_are_joined_with_a_space() -> None:
    rows = [
        ["Date", "Desc1", "Desc2", "Amount"],
        ["2024-01-05", "COFFEE", "SHOP TORONTO", "-4.50"],
    ]
    mapping = _chequing_mapping(description_columns=("Desc1", "Desc2"), date_column="Date")
    result = parse_transactions(rows, mapping)
    assert result.transactions[0].description == "COFFEE SHOP TORONTO"


def test_a_category_column_is_read_when_mapped_and_none_when_blank() -> None:
    rows = [
        ["Date", "Description", "Amount", "Category"],
        ["2024-01-05", "COFFEE SHOP", "-4.50", "Coffee"],
        ["2024-01-06", "MYSTERY", "-1.00", ""],
    ]
    mapping = _chequing_mapping(category_column="Category")
    result = parse_transactions(rows, mapping)
    assert result.transactions[0].category == "Coffee"
    assert result.transactions[1].category is None


def test_line_numbers_are_one_based_with_the_header_as_line_one() -> None:
    rows = [
        ["Date", "Description", "Amount"],
        ["2024-01-05", "FIRST", "-4.50"],
        ["2024-01-06", "SECOND", "-5.50"],
    ]
    result = parse_transactions(rows, _chequing_mapping())
    assert [t.line for t in result.transactions] == [2, 3]


def test_rows_with_no_header_are_mapped_by_position() -> None:
    rows = [["2024-01-05", "COFFEE SHOP", "-4.50"]]
    mapping = ColumnMapping(
        has_header=False,
        date_column=0,
        date_format="YYYY-MM-DD",
        description_columns=(1,),
        amount_column=2,
        sign_convention=SignConvention.CHARGES_NEGATIVE,
    )
    result = parse_transactions(rows, mapping)
    assert result.transactions[0].line == 1
    assert result.transactions[0].date == date(2024, 1, 5)


def test_a_blank_row_is_skipped_and_counted() -> None:
    rows = [
        ["Date", "Description", "Amount"],
        ["2024-01-05", "COFFEE SHOP", "-4.50"],
        ["", "", ""],
    ]
    result = parse_transactions(rows, _chequing_mapping())
    assert result.summary.rows_read == 3
    assert result.summary.rows_used == 1
    assert result.summary.skipped[0].line == 3
    assert result.summary.skipped[0].reason == "blank row"


def test_a_repeated_header_row_is_skipped_and_counted() -> None:
    rows = [
        ["Date", "Description", "Amount"],
        ["2024-01-05", "COFFEE SHOP", "-4.50"],
        ["Date", "Description", "Amount"],
    ]
    result = parse_transactions(rows, _chequing_mapping())
    assert result.summary.rows_used == 1
    assert result.summary.skipped[0].reason == "repeated header row"


def test_an_unparsable_date_is_skipped_with_a_reason() -> None:
    rows = [
        ["Date", "Description", "Amount"],
        ["not-a-date", "COFFEE SHOP", "-4.50"],
    ]
    result = parse_transactions(rows, _chequing_mapping())
    assert result.transactions == ()
    assert result.summary.skipped[0].line == 2


def test_an_unparsable_amount_is_skipped_with_a_reason() -> None:
    rows = [
        ["Date", "Description", "Amount"],
        ["2024-01-05", "COFFEE SHOP", "not-a-number"],
    ]
    result = parse_transactions(rows, _chequing_mapping())
    assert result.transactions == ()
    assert result.summary.skipped[0].line == 2


def test_date_formats_month_first_and_day_first() -> None:
    mm_dd = _chequing_mapping(date_format="MM/DD/YYYY")
    result = parse_transactions(
        [["Date", "Description", "Amount"], ["03/04/2024", "X", "-1.00"]], mm_dd
    )
    assert result.transactions[0].date == date(2024, 3, 4)

    dd_mm = _chequing_mapping(date_format="DD/MM/YYYY")
    result = parse_transactions(
        [["Date", "Description", "Amount"], ["03/04/2024", "X", "-1.00"]], dd_mm
    )
    assert result.transactions[0].date == date(2024, 4, 3)


def test_amounts_in_brackets_and_with_a_trailing_minus_are_negative() -> None:
    rows = [
        ["Date", "Description", "Amount"],
        ["2024-01-05", "A", "(4.50)"],
        ["2024-01-06", "B", "4.50-"],
    ]
    mapping = _chequing_mapping(sign_convention=SignConvention.CHARGES_POSITIVE)
    result = parse_transactions(rows, mapping)
    assert [t.amount for t in result.transactions] == [Decimal("-4.50"), Decimal("-4.50")]


def test_currency_symbols_and_thousands_separators_are_removed() -> None:
    rows = [["Date", "Description", "Amount"], ["2024-01-05", "A", "$1,234.56"]]
    mapping = _chequing_mapping(sign_convention=SignConvention.CHARGES_POSITIVE)
    result = parse_transactions(rows, mapping)
    assert result.transactions[0].amount == Decimal("1234.56")


def test_a_named_column_with_no_header_row_is_rejected() -> None:
    rows = [["2024-01-05", "COFFEE SHOP", "-4.50"]]
    mapping = ColumnMapping(
        has_header=False,
        date_column="Date",
        date_format="YYYY-MM-DD",
        description_columns=(1,),
        amount_column=2,
        sign_convention=SignConvention.CHARGES_NEGATIVE,
    )
    with pytest.raises(ValueError, match="needs a header row"):
        parse_transactions(rows, mapping)


def test_a_column_name_missing_from_the_header_is_rejected() -> None:
    rows = [["Date", "Description", "Amount"], ["2024-01-05", "A", "-1.00"]]
    mapping = _chequing_mapping(date_column="Transaction Date")
    with pytest.raises(ValueError, match="no column named"):
        parse_transactions(rows, mapping)


def test_a_date_missing_a_part_is_skipped() -> None:
    rows = [["Date", "Description", "Amount"], ["2024-01", "A", "-1.00"]]
    result = parse_transactions(rows, _chequing_mapping())
    assert result.transactions == ()
    assert result.summary.skipped[0].line == 2


def test_an_empty_amount_field_is_skipped() -> None:
    rows = [["Date", "Description", "Amount"], ["2024-01-05", "A", ""]]
    result = parse_transactions(rows, _chequing_mapping())
    assert result.transactions == ()
    assert result.summary.skipped[0].line == 2


def test_an_amount_with_no_digits_is_skipped() -> None:
    rows = [["Date", "Description", "Amount"], ["2024-01-05", "A", "-"]]
    result = parse_transactions(rows, _chequing_mapping())
    assert result.transactions == ()
    assert result.summary.skipped[0].line == 2


def test_a_debit_credit_row_with_neither_filled_is_skipped() -> None:
    rows = [["Date", "Description", "Debit", "Credit"], ["2024-01-05", "A", "", ""]]
    mapping = ColumnMapping(
        has_header=True,
        date_column="Date",
        date_format="YYYY-MM-DD",
        description_columns=("Description",),
        debit_column="Debit",
        credit_column="Credit",
    )
    result = parse_transactions(rows, mapping)
    assert result.transactions == ()
    assert "no debit or credit amount" in result.summary.skipped[0].reason


def test_a_comma_decimal_separator() -> None:
    rows = [["Date", "Description", "Amount"], ["2024-01-05", "A", "1.234,56"]]
    mapping = _chequing_mapping(
        sign_convention=SignConvention.CHARGES_POSITIVE, decimal_separator=","
    )
    result = parse_transactions(rows, mapping)
    assert result.transactions[0].amount == Decimal("1234.56")
