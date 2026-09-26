"""Tests for the `make demo` driver (ADR 0005)."""

from __future__ import annotations

import pytest

from second_look import demo


def test_demo_says_the_statement_is_made_up(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = demo.main()
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "made up" in out
    assert "not anyone's real" in out


def test_demo_statement_file_exists() -> None:
    assert demo.DEMO_STATEMENT.exists()
