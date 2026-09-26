"""The Python side of the web door's JS/Python glue (ADR 0001, ADR 0004).

This module is not part of `second_look`'s core. It runs inside Pyodide, on the
page's main thread. `app.js` fetches this file's text from the site's own origin
and runs it once with `pyodide.runPython`, which defines the functions below in
the Python global namespace. `app.js` then calls them directly: it never reimplements
column mapping or flag detection in JavaScript.

Every function here takes plain JSON-friendly arguments and returns a JSON string,
so the JS side never has to walk a Python object. The statement's bytes come in as
a JS `Uint8Array`; Pyodide's buffer protocol lets the `bytes()` built-in read it
directly, with no copy through JavaScript strings that could mangle an encoding.
"""

from __future__ import annotations

import json

from second_look import __version__, cli
from second_look.models import ColumnMapping, SignConvention

_SIGN_CONVENTIONS = {
    "charges_negative": SignConvention.CHARGES_NEGATIVE,
    "charges_positive": SignConvention.CHARGES_POSITIVE,
}


def _column_ref(value: object) -> object:
    """A column name stays a string; a position sent as a number becomes an int."""
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return value


def mapping_from_dict(data: dict) -> ColumnMapping:
    """Build a `ColumnMapping` from the mapping screen's form values."""
    amount_column = data.get("amount_column")
    debit_column = data.get("debit_column")
    credit_column = data.get("credit_column")
    category_column = data.get("category_column")
    sign_convention = data.get("sign_convention")
    return ColumnMapping(
        has_header=bool(data["has_header"]),
        date_column=_column_ref(data["date_column"]),
        date_format=data["date_format"],
        description_columns=tuple(_column_ref(c) for c in data["description_columns"]),
        amount_column=_column_ref(amount_column) if amount_column not in (None, "") else None,
        sign_convention=_SIGN_CONVENTIONS[sign_convention] if sign_convention else None,
        debit_column=_column_ref(debit_column) if debit_column not in (None, "") else None,
        credit_column=_column_ref(credit_column) if credit_column not in (None, "") else None,
        category_column=_column_ref(category_column) if category_column not in (None, "") else None,
        decimal_separator=data.get("decimal_separator", "."),
    )


def preview_rows(raw_bytes, max_rows: int = 6) -> str:
    """Decode the statement and return its first few rows as JSON, for the mapping
    screen's preview table. Uses the same decoding and delimiter-sniffing as the
    command line (ADR 0003), so the preview matches what `analyze` will actually read.
    """
    text = cli.decode_statement(bytes(raw_bytes))
    rows = cli.split_rows(text, None)
    return json.dumps({"rows": rows[:max_rows], "total_rows": len(rows)})


def analyze(raw_bytes, mapping_json: str) -> str:
    """Decode the statement, apply the user's column mapping, and run every
    detector (`second_look.cli.run`), returning the same JSON shape as
    `second-look --json` on the command line (ADR 0001: both doors give the same
    answer for the same file).
    """
    text = cli.decode_statement(bytes(raw_bytes))
    rows = cli.split_rows(text, None)
    mapping = mapping_from_dict(json.loads(mapping_json))
    try:
        flags, summary = cli.run(rows, mapping)
    except ValueError as exc:
        return json.dumps({"error": str(exc)})
    return cli.format_json(flags, summary)


def not_advice_footer() -> str:
    """The exact "not financial advice" wording (ADR 0005), read from the one
    place it is written, so the page can never drift from the command line.
    """
    return cli.NOT_ADVICE_FOOTER


def section_title() -> str:
    """The exact section title (ADR 0005), read from the one place it is written."""
    return cli.SECTION_TITLE


def tool_version() -> str:
    """The installed `second_look` version, for the feedback export (ADR 0005)."""
    return __version__
