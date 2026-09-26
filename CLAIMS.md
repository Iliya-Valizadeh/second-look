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
| After ADR 0006: wrong flags per statement, all types | 8.87 | `reports/metrics_adr0006_run.json#failure_bar.wrong_flags_per_statement` | `make eval` at commit `7852a68` |
| First run: wrong duplicate flags per statement | 5.45 | `reports/metrics.json#first_run.metrics.engine.duplicate` | `make eval` |
| Duplicate precision | 0.9808 (0.9563 to 1.0) | `reports/metrics.json#engine.duplicate.precision` | `make eval` |
| Duplicate recall | 0.9903 (0.9752 to 1.0) | `reports/metrics.json#engine.duplicate.recall` | `make eval` |
| Wrong duplicate flags per statement | 0.02 | `reports/metrics.json#engine.duplicate` | `make eval` |
| Wrong flags per statement, all types | 3.44 | `reports/metrics.json#failure_bar.wrong_flags_per_statement` | `make eval` |
| Interval level | 95% | `reports/metrics.json#interval.level` | `make eval` |
| Failure bar: recurring precision | 0.90 | `evaluation/evaluate.py` | none (a constant in the code) |
| Failure bar: duplicate and unusual precision | 0.50 | `evaluation/evaluate.py` | none (a constant in the code) |
| Generator transit fare | $3.35 | `evaluation/generator.py` | none (a constant in the code) |
| Generator coffee prices | $2.45 to $5.95 | `evaluation/merchants.py` | none (a constant in the code) |
| Recurring precision | 0.861 (0.8408 to 0.8802) | `reports/metrics.json#engine.recurring.precision` | `make eval` |
| Recurring recall | 0.9588 (0.9467 to 0.9695) | `reports/metrics.json#engine.recurring.recall` | `make eval` |
| Baseline recurring precision and recall | 0.2414, 0.7772 | `reports/metrics.json#baseline.recurring` | `make eval` |
| Recurring wrong flags and misses | 177, 47 | `reports/metrics.json#engine.recurring` | `make eval` |
| Price increase precision, recall and misses | 1.0, 0.932, 14 | `reports/metrics.json#engine.price_increase` | `make eval` |
| Unusual wrong flags and misses | 507, 85 | `reports/metrics.json#engine.unusual` | `make eval` |
| Failure bar: price increase recall, duplicate recall | 0.80 | `evaluation/evaluate.py` | none (a constant in the code) |
| Planted unusual charges | 515 | `reports/metrics.json#events.unusual` | `make eval` |
| Recurring hits with checked quality; right yearly cost share | 1093, 0.8783 | `reports/metrics.json#secondary.recurring_hit_quality` | `make eval` |
| Reference-word series, all missed | 47 | `reports/metrics.json#secondary.recurring_reference_word_recall` | `make eval` |
| Stress set: recurring recall and precision | 0.5959, 0.7816 | `reports/metrics.json#stress.recurring` | `make eval` |
| Stress set: price increase recall | 0.6402 | `reports/metrics.json#stress.price_increase` | `make eval` |
| Stress set: unusual precision | 0.2703 | `reports/metrics.json#stress.unusual` | `make eval` |
| Wrong recurring flags on ordinary spending: yearly, monthly | 109, 23 | `reports/error_analysis.json#recurring.wrong_by_source_group_and_period` | `make error-analysis` |
| Wrong recurring flags by source: groceries, restaurants, varying bill, new-price parts | 53, 31, 14 | `reports/error_analysis.json#recurring.wrong_by_source` | `make error-analysis` |
| Wrong monthly flags on ordinary spending with close but unequal amounts | 19 | `reports/error_analysis.json#recurring.background_monthly_distinct_amounts` | `make error-analysis` |
| Fixed-series hits: stopped, active with the exact cost, wrong status | 1093, 122, 960, 11 | `reports/error_analysis.json#recurring.hit_quality_detail` | `make error-analysis` |
| Missed price increases with a one-off extra charge first | 14 | `reports/error_analysis.json#price_increase.misses_with_one_off_extra_before_new_price` | `make error-analysis` |
| Charges at the new price in the missed increases, fewest and most | 58 | `reports/error_analysis.json#price_increase.misses_new_price_charges_range` | `make error-analysis` |
| Wrong unusual flags by test: merchant only, merchant and category, category only, new merchant only | 409, 30, 33, 32 | `reports/error_analysis.json#unusual.wrong_by_rule` | `make error-analysis` |
| Wrong unusual flags that involve the per-merchant score | 442 | `reports/error_analysis.json#unusual.derived` | `make error-analysis` |
| Wrong per-merchant flags by past charges at that shop | 229, 125, 55 | `reports/error_analysis.json#unusual.wrong_merchant_score_by_history` | `make error-analysis` |
| History bands used in the error analysis | 19, 20 | `evaluation/error_analysis.py` | none (labels in the code) |
| Wrong per-merchant flags by ratio to the usual amount | 183, 164, 58 | `reports/error_analysis.json#unusual.wrong_merchant_score_by_ratio` | `make error-analysis` |
| Charges scored per merchant: total, per statement, share wrongly flagged | 170,769, 854, 0.26% | `reports/error_analysis.json#unusual` | `make error-analysis` |
| Wrong unusual flags by kind of charge | 145, 125, 115, 57, 39, 18 | `reports/error_analysis.json#unusual.wrong_by_charge` | `make error-analysis` |
| Wrong new-merchant flags on shopping | 24 | `reports/error_analysis.json#unusual.wrong_new_merchant_by_charge` | `make error-analysis` |
| Missed spikes; with no category column; with a category score too low | 84, 52, 32 | `reports/error_analysis.json#unusual` | `make error-analysis` |
| Missed new-merchant charge, ratio to the typical charge | 2.97 | `reports/error_analysis.json#unusual.new_merchant_miss_ratio_to_typical` | `make error-analysis` |
| Spikes found and missed, by planted factor | 44, 48, 203, 36 | `reports/error_analysis.json#unusual` | `make error-analysis` |
| Spike recall by planted factor, then by account type | 0.4783, 0.8494, 0.6994, 0.7975 | `reports/error_analysis.json#unusual.derived` | `make error-analysis` |
| Varying bills planted, and recall on them | 200, 0.015 | `reports/metrics.json#secondary.recurring_variable_recall` | `make eval` |
| Planted price increases | 206 | `reports/metrics.json#events.price_increase` | `make eval` |
| Planted fixed-amount recurring series; refunded duplicates | 1140, 103 | `reports/metrics.json#events` | `make eval` |
| Lighthouse scores on the live page, mobile setting, first screen only: performance, accessibility | 100, 100 | `reports/metrics.json#lighthouse` | `npx lighthouse https://iliya-valizadeh.github.io/second-look/` then `python tools/lighthouse_scores.py reports/lighthouse/live_report.json` |
| Lighthouse scores served locally (before the live deploy), mobile setting, first screen only: performance, accessibility | 100, 100 | `reports/lighthouse/report.json` | `make lighthouse` |

Example row, for the format only:
`| Test AUC | 0.58 (0.55 to 0.61) | reports/metrics.json#auc | make eval |`
