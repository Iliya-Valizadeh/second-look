"""Tests for `ColumnMapping`'s own validation (ADR 0003)."""

from __future__ import annotations

import pytest

from second_look.models import ColumnMapping, SignConvention


def _base(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "has_header": True,
        "date_column": "Date",
        "date_format": "YYYY-MM-DD",
        "description_columns": ("Description",),
        "amount_column": "Amount",
        "sign_convention": SignConvention.CHARGES_NEGATIVE,
    }
    base.update(overrides)
    return base


def test_a_signed_amount_column_with_a_convention_is_valid() -> None:
    ColumnMapping(**_base())  # type: ignore[arg-type]


def test_debit_and_credit_columns_are_valid() -> None:
    mapping = _base(
        amount_column=None, sign_convention=None, debit_column="Debit", credit_column="Credit"
    )
    ColumnMapping(**mapping)  # type: ignore[arg-type]


def test_giving_both_amount_shapes_is_rejected() -> None:
    with pytest.raises(ValueError, match="not both"):
        ColumnMapping(**_base(debit_column="Debit", credit_column="Credit"))  # type: ignore[arg-type]


def test_a_signed_column_without_a_convention_is_rejected() -> None:
    with pytest.raises(ValueError, match="sign_convention"):
        ColumnMapping(**_base(sign_convention=None))  # type: ignore[arg-type]


def test_only_one_of_debit_or_credit_is_rejected() -> None:
    mapping = _base(amount_column=None, sign_convention=None, debit_column="Debit")
    with pytest.raises(ValueError, match="both debit_column and credit_column"):
        ColumnMapping(**mapping)  # type: ignore[arg-type]


def test_no_amount_shape_at_all_is_rejected() -> None:
    with pytest.raises(ValueError, match="amount_column"):
        ColumnMapping(**_base(amount_column=None, sign_convention=None))  # type: ignore[arg-type]


def test_an_unknown_date_format_is_rejected() -> None:
    with pytest.raises(ValueError, match="date_format"):
        ColumnMapping(**_base(date_format="YYYY/MM/DD"))  # type: ignore[arg-type]


def test_no_description_columns_is_rejected() -> None:
    with pytest.raises(ValueError, match="description_columns"):
        ColumnMapping(**_base(description_columns=()))  # type: ignore[arg-type]


def test_a_bad_decimal_separator_is_rejected() -> None:
    with pytest.raises(ValueError, match="decimal_separator"):
        ColumnMapping(**_base(decimal_separator=";"))  # type: ignore[arg-type]
