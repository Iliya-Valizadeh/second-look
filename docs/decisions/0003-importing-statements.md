# 0003: Importing statements

Date: 2026-09-25. Status: accepted.

## Context

Every bank exports statements in its own CSV layout. Columns differ in name and order.
Some files use one signed amount column. Others use separate debit and credit columns.
Some write dates month-first, others day-first, and a date such as `03/04/2026` fits
both. A wrong guess here does not crash. It silently turns charges into refunds or
moves every date, and every flag after that is wrong.

The rule for this project (from `_portfolio/STATUS.md` and the plan) is that no bank
format is ever guessed. Good sources for a bank's real layout are rare. Most are
forum posts or other people's code, which may be out of date.

## Options

1. A generic importer with an explicit column-mapping step. The user says which column
   holds what, sees a preview, and confirms. It works for any bank on day one.
2. Named presets for common banks, picked from what the file's header looks like. It
   is faster for the user, but only as good as the source of each preset.
3. Guess the columns and signs from the data (for example "the column with the most
   negative numbers is the amount"). No setup, but the wrong guess fails silently.

## Decision

Option 1 is the default path for every bank. Option 2 is allowed only under the
confirmation rule below. Option 3 is not used.

### The column mapping

A mapping is a small data class. It can also be saved to and loaded from a JSON file by
the doors, never by the core. It holds:

- Which row is the header, or "no header". Columns are named by header text when there
  is a header, and by position when there is not.
- The date column and its date format, chosen from a fixed list (such as `YYYY-MM-DD`,
  `MM/DD/YYYY` and `DD/MM/YYYY`).
- One or more description columns. Several are joined with a space, for banks that
  split the description in two.
- The amount, in one of two shapes:
  - one signed amount column, plus the sign convention: "charges are negative" or
    "charges are positive"
  - separate debit and credit columns, where each row fills one of them
- The decimal separator: `.` by default, or `,` when the user picks it.
- An optional category column. Without it, the per-category test in
  [ADR 0002](0002-detection-rules-and-thresholds.md) does not run.

The importer turns each row into a transaction with a date, a description, an optional
category and a `Decimal` amount where a charge is positive and money in is negative.

### Parsing rules

- Text: the core accepts bytes and decodes them as UTF-8 (a byte order mark is removed).
  If that fails, it decodes them as Windows-1252, which older Windows exports use, and
  says so in the import summary.
- Delimiter: comma, semicolon or tab, picked by `csv.Sniffer` from the first lines. The
  user can override it.
- Amounts: currency symbols, spaces and thousands separators are removed. A value in
  brackets, such as `(12.34)`, is negative. So is a value with a trailing minus, such as
  `12.34-`.
- Dates: the importer tries the chosen format on every row. When the user has not chosen
  a format, it lists every format from the list that parses all rows. If exactly one
  does, it is suggested. If more than one does, the user must choose. This happens, for
  example, when every day of the month in the file is `12` or lower, so both month-first
  and day-first read every row. The importer never picks between them on its own.
- Rows that fail to parse are not dropped in silence. The import returns a summary: rows
  read, rows used, and each skipped row's number with the reason. Fully blank rows and
  repeated header rows are skipped and counted.

### What each door does with the mapping

- The command line needs the mapping, as flags or as a mapping file. It never runs on a
  guess. It can print the parsed first rows so the user can check the signs.
- The web page can pre-fill the mapping screen from header words such as "Date" or
  "Amount". This is a suggestion only. The sign convention is never pre-filled, because
  no header word shows it reliably. The page shows the first rows as parsed (such as
  `charge $12.00` and `money in $500.00`) and runs nothing until the user confirms.

### Presets only when confirmed

A named-bank preset is a saved mapping with a bank name and a source. A preset is added
only when one of these exists:

- a URL to the bank's own help page that shows the exact header row of its CSV export
- a real header row that Iliya provides from his own export (the header line only, with
  no transaction rows)

Each preset must have:

- the source in the code, next to the preset: the URL, or "header row provided by
  Iliya" with the date
- the same source in `docs/reference.md`
- a test fixture that holds only the header row, plus a test that the preset maps it

Sources that do not count: forum posts, blogs, other open-source tools, screenshots from
third parties, and anything written from memory or by an AI assistant.

When a file's header row matches a preset's confirmed header exactly, the page
suggests that preset. The user still sees the preview and confirms.

At the time of this decision, zero presets exist. Checking the five Canadian banks named
in the plan (RBC, TD, CIBC, BMO and Scotiabank) is a later task. Every bank that stays
unconfirmed goes in `docs/whats_weak.md` as wanted.

## Consequences

- Any bank's CSV works from the first release, at the cost of one mapping step.
- A wrong mapping is still possible, but the preview makes it visible before any flag
  is computed.
- Without presets, first use is slower. This is the price of never shipping a guessed
  format.
- Real header rows are the one kind of real data this repo may hold. They carry no
  amounts, dates or names, so they carry no personal financial data.

## Option not taken

Guessing columns and signs from the data was not chosen, because a wrong guess gives
confident but wrong flags with no error to warn the user.
