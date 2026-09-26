# Reference

Facts to look up: commands, files and settings.

## Make targets

| Target | What it does |
|---|---|
| `make setup` | Installs the pinned packages with `uv` |
| `make lint` | Runs ruff and mypy |
| `make test` | Runs pytest with a coverage report for `src/` |
| `make eval` | Runs the evaluation and writes `reports/metrics.json` |
| `make demo` | Runs a short demo that needs no downloads or keys |
| `make check-docs` | Runs the claims, readability, AI-writing signs, link and README checks |
| `make error-analysis` | Sorts every wrong flag and miss on the test seeds by cause and writes `reports/error_analysis.json` |
| `make web-build` | Fetches the pinned [Pyodide](glossary.md#pyodide) files and builds the package's wheel for the web page. Needs the network |
| `make web-test` | Builds the web page, then runs its headless-browser test in Chromium |
| `make lighthouse` | Serves `web/` locally and runs Lighthouse (mobile preset) against it, then copies the performance and accessibility scores into `reports/metrics.json`. It audits the first screen only. Needs Node.js; not part of `all` since CI has no Node |
| `make all` | Runs `setup`, `lint`, `test`, `eval`, `error-analysis`, `demo` and `check-docs`, in that order |

## Output files

| File | What it holds |
|---|---|
| `reports/metrics.json` | The headline numbers, read by `CLAIMS.md` and the portfolio site |
| `reports/figures/headline.png` | The headline chart that `make eval` draws |
| `reports/error_analysis.json` | The counts by cause that `make error-analysis` writes |
| `reports/lighthouse/report.json` | The last Lighthouse report that `make lighthouse` wrote, served locally |
| `reports/lighthouse/live_report.json` | A Lighthouse report run against the live page (`iliya-valizadeh.github.io/second-look`) after the v1.0 deploy, by hand, once |

## Package

| Module | What it does |
|---|---|
| `models.py` | The data classes every other module shares: transactions, the column mapping and the four kinds of flag |
| `thresholds.py` | Every number the detection rules use, named and explained ([ADR 0002](decisions/0002-detection-rules-and-thresholds.md)) |
| `merchant.py` | Cleans a description into a merchant key for grouping |
| `importer.py` | Turns already-split CSV rows into normalized transactions ([ADR 0003](decisions/0003-importing-statements.md)) |
| `recurring.py` | Finds recurring charges and price increases on them |
| `duplicate.py` | Finds possible duplicate charges |
| `unusual.py` | Finds charges that stand out against the user's own history |
| `cli.py` | Door 1: the `second-look` command. The only module that reads a file or prints ([ADR 0001](decisions/0001-one-engine-two-doors.md)) |
| `demo.py` | Runs `cli.py` on the committed synthetic statement for `make demo` |

## Command line flags

| Flag | What it sets |
|---|---|
| `--json` | Print the flags as JSON instead of plain text |
| `--no-header` | The file has no header row; columns are then given by position, starting at `0` |
| `--date-column`, `--date-format` | The date column, and its format (`YYYY-MM-DD`, `MM/DD/YYYY` or `DD/MM/YYYY`) |
| `--description-column` | A description column; give it more than once to join several columns |
| `--category-column` | An optional category column |
| `--amount-column`, `--sign-convention` | One signed amount column, and which sign means a charge |
| `--debit-column`, `--credit-column` | Separate debit and credit columns, instead of a signed one |
| `--decimal-separator` | `.` or `,` |
| `--delimiter` | The CSV delimiter; sniffed from the file when not given |

Give either `--amount-column` with `--sign-convention`, or both `--debit-column` and
`--credit-column`, matching the column mapping in [ADR 0003](decisions/0003-importing-statements.md).

## Reason strings

Every flag carries a plain-English reason, built from one of the patterns below.
[ADR 0002](decisions/0002-detection-rules-and-thresholds.md) sets the wording, and
[ADR 0005](decisions/0005-privacy-and-wording.md) sets the words the tool never uses.
`{}` stands for a value the tool fills in: amounts as dollars with two decimals, ratios
with one decimal, percentages as whole numbers, and dates as `YYYY-MM-DD`.

| Flag | Reason pattern |
|---|---|
| Recurring | `{merchant}: {amount} charged {every week / every month / every year}, {n} times from {first} to {last}. About {yearly} a year at the latest price.` |
| Recurring, stopped | `{merchant}: {amount} charged {period}, {n} times. The last charge was {last}, so it seems to have stopped.` |
| Recurring, yearly, two charges | `{merchant}: {amount} charged twice, a year apart ({first} and {last}). About {yearly} a year if it continues.` |
| Price increase | `{merchant} went from {old} to {new} ({pct}% more) starting {date}. At the new price that adds about {yearly_diff} a year.` |
| Duplicate | `Two charges of {amount} at {merchant}, on {date1} and {date2}. The same amount at the same place within {days} days can be a double charge.` |
| Unusual, merchant | `{amount} at {merchant} on {date} is {ratio} times your usual amount there (usual: {median}, from {n} other charges).` |
| Unusual, category | `{amount} at {merchant} on {date} is {ratio} times your usual amount for {category} (usual: {median}, from {n} other charges).` |
| New merchant | `{amount} on {date} is your first charge at {merchant} in {days} days of history, and {ratio} times your typical charge ({median}).` |
| Very large | `{amount} at {merchant} on {date} is {ratio} times your typical charge ({median}).` |

A reason never guesses why a charge happened and never tells the user what to do with
their money. The section title on every screen is "Worth a second look".

## Bank CSV presets

[ADR 0003](decisions/0003-importing-statements.md) allows a named preset only when a
bank's own help page shows the exact CSV header row, or Iliya provides a real header row
from his own export. Checked on 2026-09-26, on each bank's own site only (never a
third-party page): no preset is confirmed for any of the five banks named in the plan.
Each bank's own site confirms that a CSV export exists, but none of these pages shows the
literal column header text.

| Bank | Checked, own-site page | What it shows |
|---|---|---|
| RBC | rbc.com help pages | Confirms CSV/Quicken export exists; no column header list |
| TD | td.com/ca/en/commercial-banking/wbb/help/wbwwpmyreports | Confirms CSV/BAI/tab-delimited export; no column header list |
| CIBC | cibc.com and us.cibc.com "how to" pages on downloading transactions | Confirms CSV/QFX/Excel export choices; no column header list |
| BMO | bmo.com/olbb/help-centre account-details page | Confirms CSV/Quicken/QuickBooks export; no column header list |
| Scotiabank | ScotiaConnect help, account_statement_advanced_file_exports.htm | Confirms CSV export with an "Include Headings" option; explicitly does not list header names |

All five stay unconfirmed. See `docs/whats_weak.md` for what a confirmed preset would
change. A future preset needs either a link to a bank page that shows the literal header
row, or a real header row (header only, no transactions) from Iliya.
