"""Tests for the `second-look` command line, Door 1 (ADR 0001).

This is the one module allowed to read files, so these tests write and read real
files in `tmp_path`, and read the committed synthetic fixture. No real statement is
ever used.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from second_look import cli
from second_look.models import ColumnMapping, SignConvention

FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_demo_statement.csv"


def _args(*extra: str) -> list[str]:
    return [
        str(FIXTURE),
        "--date-column",
        "Date",
        "--description-column",
        "Description",
        "--amount-column",
        "Amount",
        "--sign-convention",
        "charges-negative",
        "--category-column",
        "Category",
        *extra,
    ]


# --- column mapping --------------------------------------------------------------


def test_column_ref_reads_a_digit_string_as_a_position() -> None:
    assert cli._column_ref("2") == 2
    assert cli._column_ref("Date") == "Date"


def test_build_column_mapping_from_signed_amount_args() -> None:
    parser = cli.build_arg_parser()
    args = parser.parse_args(_args())
    mapping = cli.build_column_mapping(args)
    assert mapping == ColumnMapping(
        has_header=True,
        date_column="Date",
        date_format="YYYY-MM-DD",
        description_columns=("Description",),
        amount_column="Amount",
        sign_convention=SignConvention.CHARGES_NEGATIVE,
        category_column="Category",
    )


def test_build_column_mapping_from_debit_credit_args() -> None:
    parser = cli.build_arg_parser()
    args = parser.parse_args(
        [
            str(FIXTURE),
            "--date-column",
            "Date",
            "--description-column",
            "Description",
            "--debit-column",
            "Debit",
            "--credit-column",
            "Credit",
        ]
    )
    mapping = cli.build_column_mapping(args)
    assert mapping.debit_column == "Debit"
    assert mapping.credit_column == "Credit"
    assert mapping.amount_column is None


def test_build_column_mapping_joins_several_description_columns() -> None:
    parser = cli.build_arg_parser()
    args = parser.parse_args(
        [
            str(FIXTURE),
            "--description-column",
            "Description",
            "--description-column",
            "Memo",
            "--amount-column",
            "Amount",
            "--sign-convention",
            "charges-positive",
        ]
    )
    mapping = cli.build_column_mapping(args)
    assert mapping.description_columns == ("Description", "Memo")
    assert mapping.sign_convention is SignConvention.CHARGES_POSITIVE


def test_build_column_mapping_with_no_amount_info_raises() -> None:
    parser = cli.build_arg_parser()
    args = parser.parse_args([str(FIXTURE), "--description-column", "Description"])
    with pytest.raises(ValueError, match="amount"):
        cli.build_column_mapping(args)


def test_no_header_flag_reads_columns_by_position() -> None:
    parser = cli.build_arg_parser()
    args = parser.parse_args(
        [
            str(FIXTURE),
            "--no-header",
            "--date-column",
            "0",
            "--description-column",
            "1",
            "--amount-column",
            "2",
            "--sign-convention",
            "charges-negative",
        ]
    )
    mapping = cli.build_column_mapping(args)
    assert mapping.has_header is False
    assert mapping.date_column == 0
    assert mapping.amount_column == 2


# --- decoding and splitting --------------------------------------------------------


def test_decode_statement_reads_utf8_and_strips_the_bom() -> None:
    raw = "Date,Description,Amount\n".encode("utf-8-sig")
    assert cli.decode_statement(raw) == "Date,Description,Amount\n"


def test_decode_statement_falls_back_to_windows_1252() -> None:
    # U+2019 (a right single quote) is byte 0x92 in Windows-1252, and 0x92 alone is
    # not valid UTF-8, so decoding falls back.
    raw = "CAF’S".encode("cp1252")
    assert cli.decode_statement(raw) == "CAF’S"


def test_split_rows_sniffs_a_comma_delimiter() -> None:
    rows = cli.split_rows("Date,Description,Amount\n2024-01-01,COFFEE,4.50\n", delimiter=None)
    assert rows == [["Date", "Description", "Amount"], ["2024-01-01", "COFFEE", "4.50"]]


def test_split_rows_sniffs_a_semicolon_delimiter() -> None:
    rows = cli.split_rows("Date;Description;Amount\n2024-01-01;COFFEE;4.50\n", delimiter=None)
    assert rows == [["Date", "Description", "Amount"], ["2024-01-01", "COFFEE", "4.50"]]


def test_split_rows_honours_an_explicit_delimiter() -> None:
    rows = cli.split_rows("Date|Amount\n2024-01-01|4.50\n", delimiter="|")
    assert rows == [["Date", "Amount"], ["2024-01-01", "4.50"]]


def test_split_rows_falls_back_to_comma_when_sniffing_fails() -> None:
    rows = cli.split_rows("onecolumn\nvalue\n", delimiter=None)
    assert rows == [["onecolumn"], ["value"]]


# --- run: flags come out of a real statement ----------------------------------------


def test_run_finds_the_recurring_and_duplicate_flags_in_the_demo_statement() -> None:
    parser = cli.build_arg_parser()
    args = parser.parse_args(_args())
    mapping = cli.build_column_mapping(args)
    text = cli.decode_statement(FIXTURE.read_bytes())
    rows = cli.split_rows(text, delimiter=None)
    flags, summary = cli.run(rows, mapping)
    assert summary.rows_used == 7
    types = {flag.type for flag in flags}
    assert "recurring" in types
    assert "duplicate" in types


# --- formatting ----------------------------------------------------------------------


def test_format_text_lists_every_flag_with_its_line_numbers() -> None:
    parser = cli.build_arg_parser()
    args = parser.parse_args(_args())
    mapping = cli.build_column_mapping(args)
    text = cli.decode_statement(FIXTURE.read_bytes())
    rows = cli.split_rows(text, delimiter=None)
    flags, summary = cli.run(rows, mapping)
    output = cli.format_text(flags, summary)
    assert cli.SECTION_TITLE in output
    assert cli.NOT_ADVICE_FOOTER in output
    for flag in flags:
        assert flag.reason in output
        assert f"(line {', '.join(str(n) for n in flag.lines)})" in output


def test_format_text_says_when_nothing_is_flagged() -> None:
    output = cli.format_text([], cli.run([["Date", "Amount"]], _mapping_for_empty())[1])
    assert "Nothing worth a second look" in output


def _mapping_for_empty() -> ColumnMapping:
    return ColumnMapping(
        has_header=True,
        date_column="Date",
        date_format="YYYY-MM-DD",
        description_columns=("Date",),
        amount_column="Amount",
        sign_convention=SignConvention.CHARGES_NEGATIVE,
    )


def test_format_json_is_valid_json_with_decimal_and_date_as_strings() -> None:
    parser = cli.build_arg_parser()
    args = parser.parse_args(_args())
    mapping = cli.build_column_mapping(args)
    text = cli.decode_statement(FIXTURE.read_bytes())
    rows = cli.split_rows(text, delimiter=None)
    flags, summary = cli.run(rows, mapping)
    payload = json.loads(cli.format_json(flags, summary))
    assert payload["title"] == cli.SECTION_TITLE
    assert payload["not_financial_advice"] == cli.NOT_ADVICE_FOOTER
    assert len(payload["flags"]) == len(flags)
    for flag_dict in payload["flags"]:
        assert isinstance(flag_dict["amount"], str)  # Decimal, serialized as text


# --- main: end to end ------------------------------------------------------------------


def test_main_prints_text_by_default(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = cli.main(_args())
    assert exit_code == 0
    out = capsys.readouterr().out
    assert cli.SECTION_TITLE in out
    assert cli.NOT_ADVICE_FOOTER in out


def test_main_prints_json_with_the_flag(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = cli.main(_args("--json"))
    assert exit_code == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["title"] == cli.SECTION_TITLE


def test_main_reports_a_missing_file(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = cli.main(
        [
            "no-such-file.csv",
            "--description-column",
            "Description",
            "--amount-column",
            "Amount",
            "--sign-convention",
            "charges-negative",
        ]
    )
    assert exit_code == 2
    assert "cannot read" in capsys.readouterr().err


def test_main_reports_a_bad_mapping(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = cli.main([str(FIXTURE), "--description-column", "Description"])
    assert exit_code == 2
    assert "amount" in capsys.readouterr().err


def test_main_lists_a_skipped_row_in_the_text_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    statement = tmp_path / "statement.csv"
    statement.write_text("Date,Description,Amount\nnot-a-date,COFFEE,4.50\n")
    exit_code = cli.main(
        [
            str(statement),
            "--date-column",
            "Date",
            "--description-column",
            "Description",
            "--amount-column",
            "Amount",
            "--sign-convention",
            "charges-negative",
        ]
    )
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "skipped 1" in out
    assert "line 2:" in out


def test_main_reports_an_unknown_column_name(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad_file = tmp_path / "statement.csv"
    bad_file.write_text("Date,Description,Amount\n2024-01-01,COFFEE,4.50\n")
    exit_code = cli.main(
        [
            str(bad_file),
            "--date-column",
            "NotAColumn",
            "--description-column",
            "Description",
            "--amount-column",
            "Amount",
            "--sign-convention",
            "charges-negative",
        ]
    )
    assert exit_code == 2
    assert "NotAColumn" in capsys.readouterr().err
