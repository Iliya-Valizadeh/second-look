# ML Test Score self-assessment

This page scores this repo against the ML Test Score, a checklist from
[Breck et al. (Google, 2017)][breck]. It was scored on 2026-09-26. The scoring rule is
the one in the `ds-project-standard` template, ADR 0004, with the stricter half-point
rule used in `bank-filings-rag` and `credit-risk-scorecard`. No point is given that the
code does not earn.

## In plain words

Google wrote a list of 28 tests for a machine learning system. <!-- not-a-claim -->
A system should pass them before people rely on it.
This page checks this repo against that list. The total is one point, which is low.
The rules are tested well. But the evaluation runs by hand, and nothing watches the
tool while people use it.

## How the scoring works

The paper gives each test a score:

- none: the test is not done
- half a point: the test is done by hand, and the result is written down
- one point: the test is automated and runs again on every change

A section's score is the sum of its seven tests. The overall score is the lowest of
the four section scores, so one weak section pulls the whole system down. The paper
reads an overall score of zero as closer to a research project than a production
system. It reads a score up to one as a system that is not untested, where serious
gaps in reliability are still likely.

Following template ADR 0004, a test earns one point only after CI (continuous
integration, the checks GitHub runs on every push) has run it on GitHub. The tests
cited below passed in CI run `36234302083`, on commit `3c1ec5a` on `main`. That run
includes the Python tests, the docs checks and the headless-browser test of the web
page.

Two more rules apply, as in the other two repos. A test that CI runs but that covers
only part of what the paper asks earns half a point, not one. Tests that do not apply,
such as the serving tests, score none, as the paper does.

## What is scored

There is no trained model. The engine is a set of fixed rules with named thresholds
([ADR 0002](decisions/0002-detection-rules-and-thresholds.md),
`src/second_look/thresholds.py`). The rules and their thresholds are treated as the
"model". The "features" are the parsed transactions and the cleaned merchant key. The
evaluation on synthetic statements is in `evaluation/`, and the tests are in `tests/`
and `web/tests/`.

## Summary

| Section | Score out of 7 |
|---|---|
| Features and data | two and a half points |
| Model development | one point |
| Infrastructure | two and a half points |
| Monitoring | one point |
| Overall (the lowest section) | 1 |

Two tests earn a full point. Ten earn half a point each. The other sixteen earn
nothing.

## Tests for features and data

| # | Test | Score | Evidence or gap |
|---|---|---|---|
| 1 | Feature expectations are captured in a schema | half | `ColumnMapping` rejects a mapping that is incomplete or contradicts itself (`tests/test_models.py`). The importer turns each row into a date and an exact amount, and skips a bad row with a reason (`tests/test_importer.py`). CI runs both. Nothing checks ranges or distributions |
| 2 | All features are beneficial | none | The evaluation compares the whole engine with a simpler [baseline](glossary.md#baseline), not each rule. `reports/error_analysis.json` counts hits and wrong flags per unusual-charge rule, but no rule was left out to measure its effect |
| 3 | No feature's cost is too much | none | Not measured |
| 4 | Features adhere to meta-level requirements | half | CI checks that no core module reads files, the network, the clock or random numbers (`tests/test_architecture.py`, [ADR 0001](decisions/0001-one-engine-two-doors.md)), and that no banned word appears (`tests/test_wording.py`, `tools/banned_words_check.py`, [ADR 0005](decisions/0005-privacy-and-wording.md)). The rule that no real statement is committed rests on `.gitignore` only, and commit messages are checked by hand |
| 5 | The data pipeline has appropriate privacy controls | half | The browser test in CI records every request the web page makes on the demo statement and fails on any request to another site, any method other than GET or any query string ([ADR 0004](decisions/0004-web-door-pyodide-and-csp.md)). It runs in Chromium only. The feedback file's default of leaving out merchant names is not tested |
| 6 | New features can be added quickly | none | Not measured |
| 7 | All input feature code is tested | one point | CI covers every line of `importer.py`, `merchant.py` and `models.py`, with tests for date formats, signs, bad rows and each merchant-name cleaning step |

## Tests for model development

| # | Test | Score | Evidence or gap |
|---|---|---|---|
| 1 | Model specs are reviewed and checked in | none | The rules and thresholds are in git, with an ADR for each choice. No second person has reviewed them |
| 2 | Offline and online metrics correlate | none | There are no online metrics. The local feedback export is the only planned source, and no feedback exists yet |
| 3 | All hyperparameters have been tuned | none | Most thresholds were set by judgment in ADR 0002 and never tuned. Two rules were changed after comparisons on the tuning seeds ([ADR 0006](decisions/0006-typical-charge-for-simple-unusual-rules.md), [ADR 0007](decisions/0007-habit-test-for-duplicates.md)). Those comparisons were run by hand and are not committed |
| 4 | The impact of model staleness is known | none | The rules have no training date. Nothing tests them on older or newer spending |
| 5 | A simpler model is not better | half | `make eval` scores each detector against its baseline and gives the difference in [F1 score](glossary.md#f1-score) a 95% [bootstrap](glossary.md#bootstrap) [confidence interval](glossary.md#confidence-interval). Every interval lies above zero. It is run by hand, and the results are committed in `reports/metrics.json` |
| 6 | Model quality is sufficient on important data slices | half | `make eval` reports [precision](glossary.md#precision) and [recall](glossary.md#recall) per flag type by account type, and on a stress set. Run by hand and committed. Two flag types are below the bar set in advance ([whats_weak.md](whats_weak.md)) |
| 7 | The model is tested for considerations of inclusion | none | The synthetic data describes no real people, and nothing checks this |

## Tests for infrastructure

| # | Test | Score | Evidence or gap |
|---|---|---|---|
| 1 | Training is reproducible | half | Nothing is trained. CI checks that the same seed gives the same statement byte for byte (`tests/test_generator.py`). The evaluation writes sorted keys and no timestamp, so a rerun should give the same file. A rerun of `make error-analysis` during this scoring gave the same bytes. No CI job reruns the evaluation and compares it with `reports/metrics.json` |
| 2 | Model specs are unit tested | one point | CI covers every line of `recurring.py`, `duplicate.py` and `unusual.py`, with tests for each window, count, tolerance, exception and reason pattern |
| 3 | The ML pipeline is integration tested | half | CI runs the command line end to end on the demo statement (`tests/test_cli.py`), the web page end to end in a browser (`web/tests/test_web.py`), and the error analysis from generator to matching on four tuning seeds (`tests/test_error_analysis.py`). No test runs `evaluation/evaluate.py`, so the metric and bootstrap code is untested |
| 4 | Model quality is validated before serving | none | Nothing blocks a change that lowers precision or recall. The evaluation is not part of CI |
| 5 | The model is debuggable | half | Every flag lists its CSV line numbers and a reason that names the rule and the number that crossed the line. `evaluation/error_analysis.py` sorts every wrong flag and miss by cause ([reports/error_analysis.md](../reports/error_analysis.md)). Following one example is still done by hand |
| 6 | Models are canaried before serving | none | There is no staged release. The web page is not deployed yet |
| 7 | Serving models can be rolled back | none | There is no release process beyond git |

## Monitoring tests

| # | Test | Score | Evidence or gap |
|---|---|---|---|
| 1 | Dependency changes result in notification | none | Packages are pinned in `uv.lock`, and [Pyodide](glossary.md#pyodide) by version and hash. Nothing reports new releases |
| 2 | Data invariants hold for inputs | half | Each time someone runs the tool, the importer checks every row of their file and lists each skipped row with its reason. It never picks between month-first and day-first dates on its own. CI tests this behaviour. Nothing checks ranges, and no one but the user sees the result |
| 3 | Training and serving are not skewed | half | Both doors run the same Python package ([ADR 0001](decisions/0001-one-engine-two-doors.md)). The browser test checks that the page shows the flags `make demo` prints, on the demo statement only. The expected flag text was copied from the command line output by hand |
| 4 | Models are not too stale | none | Not measured |
| 5 | Models are numerically stable | none | Money uses exact decimals, and the score has a floor on its spread so it cannot divide by zero. No test checks for missing or infinite scores |
| 6 | Computing performance has not regressed | none | Lighthouse was run once by hand on the web page (`reports/lighthouse/`). Nothing compares it with an earlier run |
| 7 | Prediction quality has not regressed | none | No test compares a fresh evaluation with the committed numbers |

## What would raise the score

- A CI job that runs the evaluation on a few seeds and fails if a metric drops below
  the committed value. That would touch infrastructure tests 1 and 4, and monitoring
  test 7.
- A test that runs `evaluation/evaluate.py`, including the bootstrap (infrastructure
  test 3).
- Leave-one-rule-out runs of the evaluation (features and data test 2).
- Dependabot or a similar tool for new package releases (monitoring test 1).
- The browser test in Firefox and WebKit, with a check on the feedback file (features
  and data test 5).

[breck]: https://research.google/pubs/the-ml-test-score-a-rubric-for-ml-production-readiness-and-technical-debt-reduction/
