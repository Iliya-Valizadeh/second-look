"""Runs the command line on a small, committed, made-up statement for `make demo`.

This is not the engine. Like `cli.py`, it is a thin driver, so it is also allowed to
read a file and print (see the exception in `tests/test_architecture.py`). It reads no
real statement, downloads nothing and needs no key: the statement it runs on is
`tests/fixtures/synthetic_demo_statement.csv`, made up for this demo (ADR 0005).
"""

from __future__ import annotations

from pathlib import Path

from . import cli

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEMO_STATEMENT = _REPO_ROOT / "tests" / "fixtures" / "synthetic_demo_statement.csv"

DEMO_ARGS = (
    str(DEMO_STATEMENT),
    "--date-column",
    "Date",
    "--date-format",
    "YYYY-MM-DD",
    "--description-column",
    "Description",
    "--amount-column",
    "Amount",
    "--sign-convention",
    "charges-negative",
    "--category-column",
    "Category",
)


def main() -> int:
    print("This demo statement is made up for this demo. It is not anyone's real bank data.\n")
    return cli.main(DEMO_ARGS)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
