# Claims

Every number in this repo's Markdown files has a row here. Each row says where the
number comes from and which command makes that file. `make check-docs` fails if a
number in the docs has no row, or if a row does not match its source.

Small whole numbers (0 to 10), years, dates and version numbers are skipped. To skip
one line by hand, add the comment `<!-- not-a-claim -->` to it.

| Claim | Value | Source | Command |
|---|---|---|---|
| First run: recurring [precision](docs/glossary.md#precision) | 0.861 | `reports/metrics.json#first_run.metrics.engine.recurring.precision` | `make eval` |
| First run: duplicate precision | 0.1577 | `reports/metrics.json#first_run.metrics.engine.duplicate.precision` | `make eval` |
| First run: unusual precision | 0.0136 | `reports/metrics.json#first_run.metrics.engine.unusual.precision` | `make eval` |
| First run: unusual [recall](docs/glossary.md#recall) | 1.0 | `reports/metrics.json#first_run.metrics.engine.unusual.recall` | `make eval` |
| First run: unusual F1 difference, interval low end | -0.1193 | `reports/metrics.json#first_run.metrics.f1_difference.unusual` | `make eval` |
| First run: wrong unusual flags per statement | 187.17 | `reports/metrics.json#first_run.metrics.engine.unusual` | `make eval` |
| Unusual precision | 0.4589 (0.4263 to 0.4916) | `reports/metrics.json#engine.unusual.precision` | `make eval` |
| Unusual recall | 0.835 (0.8004 to 0.8677) | `reports/metrics.json#engine.unusual.recall` | `make eval` |
| Wrong unusual flags per statement | 2.535 | `reports/metrics.json#engine.unusual` | `make eval` |
| Unusual F1 difference from the [baseline](docs/glossary.md#baseline) | 0.4342 to 0.499 | `reports/metrics.json#f1_difference.unusual` | `make eval` |
| Wrong flags per statement, all types | 8.87 | `reports/metrics.json#failure_bar.wrong_flags_per_statement` | `make eval` |
| Wrong duplicate flags per statement | 5.45 | `reports/metrics.json#engine.duplicate` | `make eval` |
| Interval level | 95% | `reports/metrics.json#interval.level` | `make eval` |
| Failure bar: recurring precision | 0.90 | `evaluation/evaluate.py` | none (a constant in the code) |
| Failure bar: duplicate and unusual precision | 0.50 | `evaluation/evaluate.py` | none (a constant in the code) |
| Generator transit fare | $3.35 | `evaluation/generator.py` | none (a constant in the code) |
| Generator coffee prices | $2.45 to $5.95 | `evaluation/merchants.py` | none (a constant in the code) |

Example row, for the format only:
`| Test AUC | 0.58 (0.55 to 0.61) | reports/metrics.json#auc | make eval |`
