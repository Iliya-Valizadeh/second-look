# Changelog

All notable changes to this project are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and each release matches a
git tag.

## [1.0.0] - 2026-09-26

### Added

- Project skeleton generated from `ds-project-standard`.
- Detection rules for the data model, the merchant-name cleaner, the CSV importer,
  recurring charges and price increases (ADR 0002, ADR 0003).
- Detection rules for possible duplicate charges and unusual transactions (ADR 0002).
- The `second-look` command line, Door 1, with a column-mapping option and plain-text
  or JSON output (ADR 0001).
- `make demo`, which runs the command line on a small, committed, made-up statement.
- A test that fails if any reason string, title or label uses a word ADR 0005 bans.
- The evaluation plan, committed before any evaluation code or result
  (`docs/eval_plan.md`), the synthetic statement generator and its data tests, the
  baselines for each flag type, and `reports/metrics.json` with a
  [bootstrap](docs/glossary.md#bootstrap)
  [confidence interval](docs/glossary.md#confidence-interval) for every metric.
- An error analysis script (`make error-analysis`) that sorts every wrong flag and
  missed event on the test seeds by cause, and `reports/error_analysis.md`, which reads
  it in plain words.
- `docs/whats_weak.md`, ranking every known limit by how much it would change the
  tool's usefulness on real statements.
- `DATASHEET.md`, describing the synthetic statement dataset.
- `docs/ml_test_score.md`, scoring the repo against Breck et al.'s ML Test Score.
- Door 2, the static web page that runs `second_look` in the browser through
  [Pyodide](docs/glossary.md#pyodide), with a column-mapping screen, a
  [Content-Security-Policy](docs/glossary.md#content-security-policy-csp), and a
  local-only feedback export (ADR 0004, ADR 0005).
- A headless-browser test (Playwright) that runs the web page once on the demo
  statement and fails the build if the page makes any network request outside a fixed
  list of the site's own files.
- A check of the five named Canadian banks' own help pages for a confirmed CSV preset;
  none was found (`docs/reference.md`, `docs/whats_weak.md`).
- A Lighthouse run of the web page, wired into `reports/metrics.json`
  (`make lighthouse`).
- Diátaxis docs: `docs/tutorial.md`, `docs/how-to/`, `docs/reference.md` and
  `docs/explanation.md`, and a README rewritten to the project's house-standard
  section order.

### Changed

- The new-merchant and very-large unusual rules compare a charge with the median of the
  distinct charge amounts, not the median of all charges (ADR 0006). The first
  evaluation run showed that frequent small charges made almost every ordinary charge
  look unusual.
- The new-merchant rule counts recurring charges when it decides which charge at a
  merchant came first, as ADR 0002 says.
- The duplicate rule skips a close pair when the same merchant and exact amount
  appear on three or more dates (ADR 0007). It used to count close pairs, so a usual
  coffee order bought often was flagged as a possible double charge.
- `reports/metrics.json` keeps the first test run under `first_run`, and its failure
  bar now also gives the wrong flags per statement as a number.
- Pyodide now loads only after the user picks a file, not on page load, so the first
  page load stays small.
- `docs/eval_plan.md` gained a dated correction: the demo statement was never generator
  output at seed `9000`, and the generator's `dump_dir` argument was never built as a
  `--dump` command-line flag. Neither claim affected any reported number.
- A review pass before release made the README, the docs and the web page's text match
  the evidence. It added the first run's verdict and both eval-plan caveats to the
  README result, a note to ADR 0003 on the parts that were not built, and new items to
  `docs/whats_weak.md`.
