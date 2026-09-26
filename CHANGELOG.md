# Changelog

All notable changes to this project are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and each release matches a
git tag.

## [Unreleased]

### Added

- Project skeleton generated from `ds-project-standard`.
- Detection rules for the data model, the merchant-name cleaner, the CSV importer,
  recurring charges and price increases (ADR 0002, ADR 0003).
- Detection rules for possible duplicate charges and unusual transactions (ADR 0002).
- The `second-look` command line, Door 1, with a column-mapping option and plain-text
  or JSON output (ADR 0001).
- `make demo`, which runs the command line on a small, committed, made-up statement.
- A test that fails if any reason string, title or label uses a word ADR 0005 bans.

### Changed

- The new-merchant and very-large unusual rules compare a charge with the median of the
  distinct charge amounts, not the median of all charges (ADR 0006). The first
  evaluation run showed that frequent small charges made almost every ordinary charge
  look unusual.
- The new-merchant rule counts recurring charges when it decides which charge at a
  merchant came first, as ADR 0002 says.
- `reports/metrics.json` keeps the first test run under `first_run`, and its failure
  bar now also gives the wrong flags per statement as a number.
