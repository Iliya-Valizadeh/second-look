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
