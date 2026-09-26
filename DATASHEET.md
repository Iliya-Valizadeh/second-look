# Datasheet: synthetic statements and answer keys

Short form of the datasheet from Gebru et al., "Datasheets for Datasets"
(https://arxiv.org/abs/1803.09010). It describes the one dataset in this repo: the
synthetic bank statements made by `evaluation/generator.py`, and the answer key that
comes with each one. Every number here has a row in [CLAIMS.md](CLAIMS.md), or is a
setting quoted from the generator's spec in [docs/eval_plan.md](docs/eval_plan.md).

## In plain words

A script makes up bank statements. It also plants things the tool should find, such
as a monthly subscription or a double charge, and writes down where it put them. The
tool is then scored on how many planted things it finds. No real person's data is in
it. The statements look the way we expected bank data to look, so a good score here
does not show the tool works on real statements.

## Motivation

The dataset exists to test the four detectors in `second-look` (recurring charges,
price increases, duplicate charges, unusual charges). Real statements come with no
labels, and ADR 0005 forbids committing any real statement. A generator gives exact
labels for every planted event, and anyone can remake it from a seed.

It was written for this project by the same person who wrote the detection rules
([ADR 0002](docs/decisions/0002-detection-rules-and-thresholds.md)), after those rules.
The spec was committed in `docs/eval_plan.md` before any generator code or result.

## Composition

One statement is one CSV text, one column mapping and one answer key, all made from
one seed. One CSV row is one transaction: a date, a description and an amount, plus a
category on credit card statements.

Two made-up account layouts, neither of them a real bank's format:

- chequing (even seeds): `Date,Description,Amount`, dates as `YYYY-MM-DD`, one signed
  amount, oldest row first, a payroll deposit every `14` days
- credit card (odd seeds): `Transaction Date,Description,Category,Debit,Credit`, dates
  as `MM/DD/YYYY`, newest row first, one card payment a month

Each statement covers `6` to `24` whole months, starting on a random day in 2023 or
2024. Its rows are:

- background spending in eight categories (groceries, restaurants, coffee, transit,
  fuel, shopping, pharmacy, entertainment) at invented merchants, with amounts from a
  log-normal draw, a fixed coffee menu and a fixed transit fare
- planted recurring charges: `3` to `8` subscriptions (monthly, weekly or yearly),
  rent on chequing statements, and one bill whose amount varies
- planted price increases, duplicate charges (some refunded) and unusual charges
- decoys: one-off extra charges at a subscription, and refund rows

The answer key lists every planted event and decoy by CSV line number, never by
merchant name, so a mistake in cleaning merchant names shows up as a miss.

### Size of the sets used

| Set | Seeds | Statements | Use |
|---|---|---|---|
| Test | `1000` to `1199` | `200` | the reported results |
| Tuning | `0` to `99` | `100` | building, debugging and any tuning |

Planted events in the test set, from `reports/metrics.json`:

| Event | Count |
|---|---|
| Fixed-amount recurring series | 1140 |
| Varying-amount recurring bills | 200 |
| Price increases | 206 |
| Duplicates, not refunded | 206 |
| Duplicates, refunded | 103 |
| Unusual charges | 515 |

Half the test statements are chequing and half are credit card, by seed parity. Only
the credit card half has a category column.

## Collection

Nothing was collected. Every row comes from `generate_statement(seed)` in
`evaluation/generator.py`, which uses one `random.Random(seed)` and no other source of
randomness. The same seed gives the same bytes, and a test checks this. Merchant
names are invented (`evaluation/merchants.py`). None is meant to be a real company.

The generator's version is `GENERATOR_VERSION = "1"`. Any change that alters output
for a seed must bump it.

## Preprocessing

None. The evaluation passes each generated CSV text through the engine's real
importer with its column mapping, so parsing is part of what is tested. No rows are
cleaned, dropped or changed on the way.

## Uses

It fits:

- checking that the detectors find what they were designed to find
- comparing the engine with its simple [baselines](docs/glossary.md#baseline)
- tracing wrong flags to their cause ([reports/error_analysis.md](reports/error_analysis.md))
- a stress test that pushes events past the rules' windows (`stress=True`)

It should not be used for:

- claiming accuracy on real bank statements
- training or tuning a model meant for real data, since its spending patterns are
  invented
- any statement about how real people spend

## Known limitations

- It is synthetic. Real merchant names, posting delays, price changes and spending
  habits are not copied.
- The generator was designed by someone who knew the rules. Several choices sit near
  the rules' thresholds on purpose, but the risk that the generator fits the rules
  remains ([docs/eval_plan.md](docs/eval_plan.md), "What this test can and cannot
  show").
- Every planted recurring series has at least the number of charges the rules need,
  and its gaps sit inside the rules' windows (outside the stress set). This makes
  [recall](docs/glossary.md#recall) easier than on a real statement.
- Frequent small charges repeat exact amounts (a fixed transit fare and a four-price
  coffee menu). ADR 0006's fix works best on exactly this pattern, so the unusual
  result is likely better here than on real data.
- The generator never plants a double charge at a price the person pays often. So it
  cannot measure the cost ADR 0007 accepted.
- It does not make series every two weeks, three months or six months, yearly price
  increases, or real bank layouts. The column mapping is always given correctly.
- One label gap is known. The generator's ordinary refunds can refund the original of
  a planted duplicate, while the answer key still counts the pair as unrefunded
  (ADR 0007). This causes both of the engine's duplicate misses in the test set.

## Distribution and maintenance

No generated statement is committed. Anyone can remake one with
`generate_statement(seed)`, and pass `dump_dir` to write the CSV and answer key to a
folder. The eval plan asked for a `--dump DIR` command-line flag. It exists only as
this function argument. The code is under the repo's MIT license. Iliya Valizadeh maintains
it in this repo.

The demo statement `tests/fixtures/synthetic_demo_statement.csv` is not generator
output. It is a short hand-written file. The eval plan names seed `9000` for the demo;
that swap has not been made.
