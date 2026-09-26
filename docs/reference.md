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
| `make all` | Runs every step above in order |

## Output files

| File | What it holds |
|---|---|
| `reports/metrics.json` | The headline numbers, read by `CLAIMS.md` and the portfolio site |
| `reports/figures/mae_by_model.png` | The headline chart that `make eval` draws |

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
