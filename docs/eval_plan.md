# Evaluation plan

This plan was written and committed before any evaluation code or result existed. The
README links to the commit that added it, so a reader can check that the plan came
first. Later tasks build the generator and the evaluation to match this file. If
anything changes, it goes under "Changes to this plan" with a date and a reason. It is
never edited in silence.

## What this test can and cannot show

Read this before any number from this evaluation.

Every statement in this test is synthetic. A script made it, and the same script wrote
down where it planted each recurring charge, price increase, double charge and unusual
charge. The test measures one thing: whether the detection rules in
[ADR 0002](decisions/0002-detection-rules-and-thresholds.md) find what was deliberately
planted, and how many wrong flags they raise on the synthetic background spending.

It cannot show how well the tool works on real bank statements. Real statements have
merchant names, posting delays, price changes and spending habits that this generator
does not imitate. A high score here means the rules do what they were written to do on
data shaped the way we expected. It does not mean they are accurate for real people.

There is a second limit. This plan was written after ADR 0002, by the same project, with
its thresholds in view. The generator's choices were made by someone who knew what the
rules look for. Several choices below push events near or past the thresholds on
purpose (they are listed under "Decoys and hard cases" and in the stress set). Even so,
the risk that the generator fits the rules remains, and it cannot be removed by this
test.

Two later files must carry this caveat in plain words:

- the README "Result" section, in the same paragraph as the headline number
- `docs/whats_weak.md`, as its first item

The review task before merge checks both.

## Question

On synthetic statements with known planted events, how often does each of the four
detectors find the planted events, how often are its flags right, and does it do better
than a simpler method?

## Order of work and the freeze rule

1. Build the generator and its data tests. Use only the tuning seeds (below).
2. Build the baselines, the matching code and the evaluation script. Debug them on the
   tuning seeds only.
3. Commit the generator, baselines and evaluation. Then run the test seeds for the
   first time. Write the commit hash of that first run under "Changes to this plan".
4. The first test run, at the ADR 0002 thresholds as written, is the one judged against
   the failure bar. It is always reported, even if something changes later.

Any change to a threshold, the generator or the matching after that first test run is a
deviation. It goes under "Changes to this plan", and `reports/metrics.json` then holds
both the first result and the new one. Thresholds may be tuned only on the tuning seeds,
never on the test seeds (ADR 0002 says the same).

## The synthetic statement generator

### Where it lives

The generator uses `random`, and ADR 0001 forbids `random` and file access in the core
package. So the generator, the baselines and the evaluation script live outside
`src/second_look/`, in a top-level `evaluation/` folder. The evaluation task changes the
`make eval` target to run it. These files may read and write files. They call the
engine only through its public functions, the same way the command line does.

The generator returns three things per statement, in memory: the CSV text, the column
mapping for it, and the answer key. The evaluation passes the CSV text through the real
importer with that mapping, so parsing is part of what is tested. Nothing generated is
committed, except the one small demo statement (seed below). An optional `--dump DIR`
flag writes the three files for anyone who wants to look at them.

### Randomness

Each statement uses one `random.Random(seed)` object and nothing else. Draws happen in
this fixed order: account type, length and dates, background spending, recurring
charges, price increases, decoys, duplicates, unusual charges, refunds, then sorting and
writing. The generator has a version string, `GENERATOR_VERSION = "1"`. Any change that
alters output for a seed bumps it.

### Account types

There are two account types. Each has its own invented CSV layout. These layouts are
made up for the test. They are not any bank's real format.

| Account type | Which seeds | Header row | Date format | Amount columns | Row order |
|---|---|---|---|---|---|
| Chequing | even seeds | `Date,Description,Amount` | `YYYY-MM-DD` | one signed column, charges negative | oldest first |
| Credit card | odd seeds | `Transaction Date,Description,Category,Debit,Credit` | `MM/DD/YYYY` | separate debit and credit | newest first |

So the test seeds give exactly half of each. Only the credit card statements have a
category column, so the per-category unusual test runs on half the statements.

Money coming in:

- Chequing: a payroll deposit every `14` days. The first falls on a random day in the
  first `14` days. The amount is fixed per statement, drawn from `1800` to `3200`
  dollars in whole dollars.
- Credit card: one payment per calendar month on day `20`, equal to the total charges
  of the previous calendar month. The first month has no payment.

### Length and dates

- Length: a whole number of months, drawn evenly from `6` to `24`.
- Start date: drawn evenly from `2023-01-01` to `2024-12-31`. The statement covers
  whole calendar days from the start date to the day before the same day-of-month,
  that many months later.
- The engine's "today" is the last date in the file (ADR 0001). The answer key uses the
  same date when it decides whether a series is active.

### Background spending

Background charges are ordinary spending. They are not events. Any flag on them is a
wrong flag.

Merchant names are invented. The generator must not use the name of a real company. The
description formats copy common patterns, so the merchant-name cleaning in ADR 0002 is
exercised:

- Half the coffee and restaurant merchants start with `SQ *`.
- Grocery, fuel and pharmacy merchants carry a store number such as `#482`. Each has
  `1` to `3` store numbers, and each visit picks one of them.
- Every background merchant ends with a city and a province code, such as
  `TORONTO ON`. Each merchant has one city.
- A quarter of the merchants end with `INC` or `LTD` before the city.

Visits are counted per calendar month, drawn evenly from the range in the table. Each
visit lands on a random day of that month. Within a category, the merchant is picked
with weights `1`, `1/2`, `1/3` and so on, so each person has a favourite shop. Amounts
use a log-normal draw with the given median and spread (`sigma`, on the natural log
scale), rounded to the cent. Each merchant's own median is the category median times a
factor drawn once per statement, evenly from `0.7` to `1.3`.

| Category | Merchants | Visits per month | Amount |
|---|---|---|---|
| Groceries | `4` | `4` to `8` | median `60`, sigma `0.5` |
| Restaurants | `8` | `2` to `6` | median `32`, sigma `0.5` |
| Coffee | `3` | `6` to `14` | one of `2.45`, `3.25`, `4.75`, `5.95` |
| Transit | `1` | see below | always `3.35` |
| Fuel | `3` | `1` to `3` | median `55`, sigma `0.25` |
| Shopping | `6` | `1` to `4` | median `40`, sigma `0.7` |
| Pharmacy | `2` | `0` to `2` | median `22`, sigma `0.6` |
| Entertainment | `3` | `0` to `2` | median `28`, sigma `0.4` |

Transit: on each weekday, with probability `0.3`, there are two fares that day (going
and coming back). Coffee draws from a short menu, so the same amount at the same shop
comes up often. Both are there on purpose, as hard cases for the duplicate rule.

Refunds: each shopping charge is refunded in full with probability `0.05`, `3` to `20`
days later, if that date is inside the statement. The refund row uses the same
description.

### Planted recurring charges

Each statement gets:

- `3` to `8` subscriptions (drawn evenly), each at its own merchant
- one monthly rent payment, on chequing statements only
- one monthly bill with a varying amount, such as electricity

Subscription merchants come from a list of at least `20` invented names, separate from
the background merchants.

| Period | Chance | Amounts (dollars) | Posting delay |
|---|---|---|---|
| Monthly | `0.75` | one of `4.99`, `7.99`, `9.99`, `11.99`, `14.99`, `16.99`, `19.99`, `24.99`, `34.99`, `49.99`, `64.99`, `89.99` | `0` to `3` days |
| Weekly | `0.10` | one of `3.99`, `5.99`, `8.99`, `12.99`, `59.99`, `74.99` | `0` to `1` day |
| Yearly | `0.15` | one of `39.99`, `59.99`, `79.99`, `99.99`, `119.99`, `139.99` | `0` to `3` days |

How the dates are made:

- A monthly series has a billing day of the month, drawn from `1` to `31`. In a month
  that is too short, it falls on the last day. A weekly series has a billing weekday. A
  yearly series has a billing date.
- Each charge posts on its billing date plus the posting delay, drawn per charge.
- A yearly subscription needs two charges inside the statement. If the statement is
  shorter than `13` months, the draw becomes monthly instead.
- A series is planted only if it has at least the number of charges ADR 0002 needs
  (`4` weekly, `3` monthly, `2` yearly). No method could tell a shorter series from
  chance. This makes [recall](glossary.md#recall) easier than on a real statement, where a subscription may
  have started last month.

Variations, drawn per subscription:

- Late start, probability `0.2`: the first charge is at a random point after the first
  period, as long as the minimum count still fits.
- Stopped, probability `0.15`: the last charge is at least two periods before the
  statement end, as long as the minimum count still fits.
- Skipped charge, probability `0.10` (weekly and monthly only, and only when the series
  has at least one charge more than the minimum): one charge that is not the first or
  the last is removed.
- Foreign currency, probability `0.15`: each charge is multiplied by a factor drawn
  evenly from `0.99` to `1.01`, then rounded to the cent.
- Changing reference number, probability `0.3`: each charge's description ends with a
  new 8-digit number. The cleaning step in ADR 0002 removes it.
- Changing reference word, probability `0.05`: each charge's description ends with a
  new random 3-letter code. ADR 0002 says these will not group, so they are expected
  misses. They stay in the recall count.

Rent: monthly, amount from `1400` to `2600` dollars in steps of `50`, billing day `1`,
posting delay `0` to `2` days, with a changing reference number. It has no other
variations.

Varying bill: monthly, base amount drawn evenly from `60` to `180` dollars, and each
charge is the base times a factor drawn evenly from `0.85` to `1.15`. ADR 0002 does not
aim to catch these, because the amounts differ by more than three percent. They are
scored apart from the other recurring charges (see "Metrics").

### Planted price increases

- Which series can get one: weekly and monthly subscriptions without a changing
  reference word. Not rent, not the varying bill, not yearly series. A yearly increase
  needs about three years of history, which the statements do not have.
- Chance: `0.25` per series that can get one.
- Where: at a charge picked evenly among those that leave at least the minimum count
  before it (`3` monthly, `4` weekly) and at least `2` charges from it onward.
- Size: the old amount times `1 + p`, with `p` drawn evenly from `0.05` to `0.30`, then
  rounded up to the next amount ending in `.99`. Foreign-currency noise is applied after
  that.
- The whole series, before and after the increase, is still one recurring event.

### Planted duplicate charges

- Count: `0` to `3` per statement, drawn evenly.
- Each one copies a background charge from groceries, restaurants, fuel, shopping,
  pharmacy or entertainment. The copy has the same description and amount. It posts
  `0`, `1` or `2` days after the original, drawn evenly, and not after the last day.
- Refunded, probability `0.3`: a refund row of the same amount and description is added
  `3` to `10` days after the copy. Only copies at least `10` days before the last day
  can be refunded. ADR 0002 says a refunded pair must not be flagged, so a flag on it is
  a wrong flag.

### Planted unusual charges

- Count: `1` to `4` per statement, drawn evenly.
- Kind, drawn per charge:
  - Spike at a known merchant, probability `0.6`. Pick a background merchant from the
    same six categories as duplicates, with at least `6` background charges in the
    statement. The amount is that merchant's median charge in this statement times a
    factor drawn evenly from `3` to `10`, rounded to the cent. It must be at least `25`
    dollars, or another merchant is picked. The date is any day of the statement. The
    lower end of `3` comes from the plan's own example ("three times your usual amount")
    and sits below what a merchant with a wide spread needs to score above `3.5`. Some
    of these are meant to be hard.
  - Large charge at a new merchant, probability `0.4`. A merchant from a separate list
    of at least `10` invented one-time merchants (electronics, furniture, travel, car
    repair). The amount is drawn evenly from `150` to `900` dollars, rounded to the
    cent. The date is day `61` or later.
- If no merchant qualifies for a spike, the charge becomes the new-merchant kind.

### Decoys and hard cases

Decoys are not events. They are listed in the answer key only so the error analysis
can find them. Any flag on a decoy is a wrong flag.

- One-off extra at a subscription merchant, probability `0.10` per weekly or monthly
  subscription: one extra charge of the subscription amount times `1.2` to `2.0`, on a
  day at least `3` days from any regular charge. This tests the rule that a new price
  must hold for `2` charges.
- Transit fares and the coffee menu (above): same merchant, same amount, same or next
  day. These test the habit exception in the duplicate rule.
- Refunded duplicates (above).

Hard cases that are events: posting delays, skipped charges, foreign-currency noise,
late starts, stopped series, changing reference words, and spikes as small as three
times the usual amount.

A transaction belongs to at most one planted event or decoy, except that a price
increase sits inside its recurring series.

### What the generator does not produce

These are real situations the test says nothing about:

- series every two weeks, every three months or every six months (ADR 0002 misses them)
- yearly price increases
- time of day, which bank CSV files do not carry
- merchants whose description changes in ways other than the ones above
- real bank layouts, sign mistakes and date-format mix-ups (the mapping is always given
  correctly)
- the behaviour of any real person

## The answer key

One JSON object per statement. Amounts are strings with two decimals, so they stay
exact. A line is the 1-based line number in the CSV text, so the header is line `1` and
the first data row is line `2`. Rows are referred to by line, never by merchant name,
so a mistake in merchant-name cleaning shows up as a miss.

```json
{
  "seed": 1000,
  "generator_version": "1",
  "stress": false,
  "account_type": "chequing",
  "first_date": "2024-03-14",
  "last_date": "2025-09-13",
  "events": [
    {"id": "rec-01", "type": "recurring", "kind": "fixed", "period": "monthly",
     "description": "...", "lines": [5, 40, 77], "active": true,
     "expected_yearly_cost": "119.88", "foreign_currency": false,
     "skipped_one": false, "reference_number": true, "reference_word": false},
    {"id": "rec-07", "type": "recurring", "kind": "variable", "period": "monthly",
     "lines": [9, 44, 80], "active": true},
    {"id": "pri-01", "type": "price_increase", "series": "rec-01",
     "old_amount": "9.99", "new_amount": "11.99", "first_new_line": 77},
    {"id": "dup-01", "type": "duplicate", "lines": [120, 121], "refunded": false},
    {"id": "unu-01", "type": "unusual", "kind": "spike_known_merchant",
     "line": 300, "factor": 4.2},
    {"id": "dec-01", "type": "decoy", "kind": "one_off_extra", "line": 88}
  ]
}
```

The values above show the format only. They are not output from any run.

Field rules:

- `recurring` events list every line of the series, including the lines after a price
  increase. `kind` is `fixed` for subscriptions and rent, and `variable` for the
  varying bill. `active` and `expected_yearly_cost` follow ADR 0002 exactly: active if
  the last charge is no more than `1.5` periods before the last date, and yearly cost is
  the latest amount times `52`, `12` or `1`, only for active series.
- `price_increase` events point at their series and give the first line at the new
  price.
- `duplicate` events list the original line and the copy line, in that order.
- `unusual` events give the one planted line.
- Kinds for unusual events are `spike_known_merchant` and `large_new_merchant`. Kinds
  for decoys are `one_off_extra` and `refunded_duplicate_refund` (the refund row).

## What the engine must expose

The engine is built after this plan, so it can meet these needs from the start. Every
flag carries:

- `type`: one of `recurring`, `price_increase`, `duplicate`, `unusual`
- `lines`: the CSV line numbers of the transactions it covers, taken from the importer

And per type:

- recurring: every line in the series, plus `period`, `active` and `yearly_cost`
- price increase: the lines of the charges at the new price, in date order, plus
  `old_amount` and `new_amount`
- duplicate: the two lines
- unusual: the one line (several reasons on one charge are still one flag)

## Matching a flag to a planted event

Matching is one-to-one. Each event matches at most one flag, and each flag at most one
event. A matched pair is a hit. A flag with no match is a wrong flag. An event with no
match is a miss. Every rule compares line numbers, so it can be computed exactly.

Recurring:

- A flag and a recurring event (fixed or variable) are a candidate pair when their
  shared lines are at least half of the flag's lines and at least half of the event's
  lines.
- Candidate pairs are taken greedily: most shared lines first, then the lower event id,
  then the earlier flag in the engine's output. A pair is taken only if neither side is
  already matched.
- A split series (for example the old price and the new price listed apart) leaves at
  most one part matched. The other part counts as a wrong flag.

Price increase:

- A hit when the flag's lines include the event's `first_new_line`, and the flag's new
  amount is within the ADR 0002 close-amount tolerance of the key's `new_amount` (the
  larger of `0.05` dollars and three percent of the smaller amount).

Duplicate:

- A hit when the flag's two lines are exactly the event's two lines, in any order, and
  the event is not refunded.
- A flag on a refunded duplicate is a wrong flag.

Unusual:

- A hit when the flag's line is the event's line.

## Metrics

Per flag type, counts are pooled over all test statements:

- [Precision](glossary.md#precision): hits divided by all flags of that type.
- [Recall](glossary.md#recall): hits divided by the planted events of that type that
  should be found.
- [F1 score](glossary.md#f1-score): `2 * precision * recall / (precision + recall)`.
  It is used only to compare the engine with its [baseline](glossary.md#baseline).
- Wrong flags per statement: the mean over statements of flags with no match.

Which events count for recall:

- Recurring: `fixed` series only. A flag that matches a `variable` series still counts
  as a hit for precision, because it points at a real recurring charge. Recall on
  `variable` series is reported apart, as a secondary check.
- Price increase: every planted price increase.
- Duplicate: every duplicate that was not refunded.
- Unusual: every planted unusual charge.

Secondary checks, reported but not judged:

- Among recurring hits: the share with the right period, the right active or stopped
  status, and (for active series) a yearly cost equal to the key's to the cent.
- Recall on `variable` recurring series.
- Recall on series with a changing reference word (expected to be near zero).
- The number of refunded duplicates that were flagged.
- Precision and recall per flag type, split by account type.
- The stress set (below).

## Baselines

Each flag type gets one simpler method to beat. Each [baseline](glossary.md#baseline)
uses the engine's own merchant-name cleaning, so the comparison isolates the rule
logic. Baseline flags are matched and scored exactly like engine flags.

| Flag type | Baseline | What the engine adds |
|---|---|---|
| Recurring | Group charges by merchant key and exact amount. Any group with at least `3` charges is one recurring flag with all its lines. | spacing checks, amount tolerance, minimum counts per period |
| Price increase | For each baseline recurring group, flag the first later charge at the same merchant key whose amount is above the group amount by more than the close-amount tolerance. Its lines are that one charge. | the new price must repeat, at the same spacing |
| Duplicate | Same merchant key, exact same amount, dates no more than `2` days apart. Within one merchant key and amount, each two charges next to each other in date order that meet this are a flag. | the refund exception and the habit exception |
| Unusual | Ordinary z-score on the raw amounts of all charges in the statement (mean and standard deviation). Flag every charge more than `3` standard deviations above the mean. | median-based scores per merchant and per category, history minimums, the ratio and dollar floors, and the two simple rules |

The unusual baseline is the method ADR 0002 turned down (ordinary z-scores), so the
comparison tests that choice directly.

## How many statements and which seeds

| Set | Seeds | Statements | Use |
|---|---|---|---|
| Test | `1000` to `1199` | `200` | the reported results |
| Tuning | `0` to `99` | `100` | building, debugging, any threshold tuning |
| Demo | `9000` | `1` | the committed synthetic statement for `make demo` and the web page test |

The sets do not overlap. With the counts above, the test set should hold roughly a
thousand fixed recurring series and a few hundred of each other event type, so the
intervals will not be too wide to read. The exact counts go in `metrics.json` from the
run itself.

## Intervals

The [confidence interval](glossary.md#confidence-interval) for every metric comes from
a [bootstrap](glossary.md#bootstrap) over statements, not over single events. Events in
one statement share merchants, length and account type, so they are not independent.
An interval on pooled counts (such as a Wilson interval) would treat them as
independent and come out too narrow.

- Draw `200` statements from the `200` test statements, with repeats allowed.
- Pool the counts over the drawn statements and compute every metric.
- Repeat `2000` times with `random.Random(4242)`.
- Sort the values. The interval runs from the `51st` smallest to the `1950th` smallest,
  which is a `95%` interval.
- If a draw has no flags (or no events) for a metric, that draw is skipped for that
  metric, and the number skipped is written in `metrics.json`.
- For the engine against its baseline, both are scored on the same draws. The
  difference in F1 score gets its own interval from those same draws.

## The headline number

The README headline is the engine's recall on planted fixed-amount recurring charges
over the `200` test statements, with its `95%` interval. It is always shown in the same
sentence as the recurring precision and the baseline's recall and precision. The
README sentence follows this pattern, with values from `metrics.json`:

`On 200 synthetic statements, it found {recall} of the planted recurring charges ({low} to {high}), and {precision} of its recurring flags were right. The simpler baseline found {b_recall} at {b_precision}.`

Why this one: recurring charges with their yearly cost are the feature the tool leads
with. It is not chosen because it is expected to score best. It is probably the easiest
of the four, since the planted series are regular by construction. The README must say
that next to it. The headline chart shows all four flag types, so a weak type cannot
hide behind the headline.

The headline chart: precision and recall per flag type, engine next to baseline, with
the interval as a line on each bar. The caption says what to notice.

## What counts as failure

Decided now, before any result. The judgment uses the first test run, at the ADR 0002
thresholds as written, and the point values from it.

The approach did not work if any of these hold:

| Check | Fails when |
|---|---|
| Recurring | recall below `0.90`, or precision below `0.90` |
| Price increase | recall below `0.80`, or precision below `0.80` |
| Duplicate | recall below `0.80`, or precision below `0.50` |
| Unusual | recall below `0.50`, or precision below `0.50` |
| Each flag type against its baseline | the `95%` interval of the engine's F1 score minus the baseline's F1 score does not lie fully above zero |
| All flags together | more than `5` wrong flags per statement on average |

Why these bars:

- Recurring series are planted regular and within the rule's windows. If the rules
  miss one in ten of their own kind of series, or one flag in ten is wrong, something
  is broken.
- Price increases are exact rules on top of a found series, so the bar is also high.
- Duplicates allow lower precision because the transit and coffee decoys are hard on
  purpose. Below `0.50`, a user sees more wrong duplicate flags than right ones.
- Unusual charges are the fuzziest type. Below `0.50` on either side, a user sees more
  wrong flags than right ones, or the tool misses most planted charges.
- A list with more than `5` wrong items per statement buries the right ones.
- An engine that cannot beat a simpler method with a clear margin does not justify its
  extra rules.

If a check fails:

- The README "Result" section says the result did not meet the bar set in advance, and
  names the check.
- `docs/whats_weak.md` puts it right after the synthetic-data caveat.
- The thresholds may be tuned on the tuning seeds, with a dated deviation here. Both
  the first result and the tuned result stay in `metrics.json` and the README.

A prediction, written now: the very-large rule and the new-merchant rule in ADR 0002
compare a charge with the median of all charges in the statement. Transit fares and
coffee pull that median down. So these two rules may raise many wrong flags on
ordinary grocery and restaurant charges. If that happens, the error analysis should
say so, and any fix goes through the tuning seeds.

## What would change the conclusion

The stress set reruns the test seeds with the generator's `stress=True` setting. It
changes only these draws:

- posting delay `0` to `5` days for every period
- foreign-currency factor from `0.975` to `1.025`
- changing reference word, probability `0.20`
- spike factor from `2` to `5`

It reports precision and recall per flag type. It is not judged against the failure
bar. It shows how fast the rules break when the data moves past the ADR 0002 windows
and tolerances. A large drop there means the main result depends on the generator
staying inside those limits, and the README must say so.

A split by account type that shows a large gap (for example unusual-charge recall with
and without a category column) would also narrow what the main numbers mean.

None of this measures real statements. The local feedback export on the web page is
the only path to real-world evidence, and it stays on the user's machine.

## Output: `reports/metrics.json`

The evaluation writes one JSON file with sorted keys and floats rounded to 4 decimal
places, so a rerun gives the same bytes. It holds no git hash or timestamp for the same
reason. The shape, with names the README and `CLAIMS.md` will point at:

```json
{
  "generator_version": "1",
  "test_seeds": {"first": 1000, "last": 1199, "statements": 200},
  "interval": {"method": "statement_bootstrap_percentile", "resamples": 2000,
               "level": 0.95, "seed": 4242},
  "events": {"recurring_fixed": 0, "recurring_variable": 0, "price_increase": 0,
             "duplicate": 0, "duplicate_refunded": 0, "unusual": 0},
  "engine": {
    "recurring": {
      "precision": {"value": 0.0, "ci_low": 0.0, "ci_high": 0.0},
      "recall": {"value": 0.0, "ci_low": 0.0, "ci_high": 0.0},
      "f1": {"value": 0.0, "ci_low": 0.0, "ci_high": 0.0},
      "hits": 0, "wrong_flags": 0, "misses": 0,
      "wrong_flags_per_statement": 0.0, "skipped_resamples": 0
    },
    "price_increase": {}, "duplicate": {}, "unusual": {}
  },
  "baseline": {"recurring": {}, "price_increase": {}, "duplicate": {}, "unusual": {}},
  "f1_difference": {"recurring": {"value": 0.0, "ci_low": 0.0, "ci_high": 0.0}},
  "secondary": {},
  "stress": {},
  "headline": {"name": "engine.recurring.recall", "value": 0.0,
               "ci_low": 0.0, "ci_high": 0.0},
  "failure_bar": {"passed": false, "failed_checks": []}
}
```

The zeros are empty slots for the format, not results. The evaluation task fills every
empty object with the same fields as `engine.recurring`.

The headline chart goes to `reports/figures/`, and `make eval` and `make all` rebuild
both files.

## Data tests on the generator

The evaluation task adds tests that check, on the tuning seeds:

- the same seed gives the same CSV text and the same answer key, byte for byte
- every count and amount falls inside the ranges in this plan
- every line in the answer key exists, and its row has the amount the key says
- every planted weekly, monthly and yearly series (outside the stress set) has gaps
  inside the ADR 0002 windows and at least the minimum count
- no line belongs to two events, except a price increase inside its series
- the importer reads every generated statement with no skipped rows

## Changes to this plan

### First test run

The first test run is commit `f532add`, at the ADR 0002 thresholds as written. Step 3
above asked for this hash when the run was made. It was added here on 2026-09-26, with
the change below.

That run did not pass the failure bar. Its own `failure_bar.failed_checks` list, kept
in `reports/metrics.json` under `first_run`:

- recurring precision 0.861, below 0.90
- duplicate precision 0.1577, below 0.50
- unusual precision 0.0136, below 0.50
- the unusual F1 difference from the baseline did not lie above zero (interval low end
  -0.1193)
- more than 5 wrong flags per statement across all types

The prediction under "What counts as failure" was right about the cause of the unusual
result. See [ADR 0006](decisions/0006-typical-charge-for-simple-unusual-rules.md).

### 2026-09-26: typical charge in the simple unusual rules

What changed: the new-merchant and very-large rules now compare a charge with the median
of the distinct charge amounts, leaving out the charge being judged, instead of the
median of all charges. The new-merchant rule also counts recurring charges when it
decides which charge at a merchant came first, as ADR 0002 already said.
[ADR 0006](decisions/0006-typical-charge-for-simple-unusual-rules.md) gives the
diagnosis and the reasons.

What did not change: every number in `src/second_look/thresholds.py`, the generator,
the matching, the metrics, the baselines and the failure bar.

How it was chosen: on the tuning seeds (`0` to `99`) only. The test seeds were then run
once more.

Where the results are: `reports/metrics.json` holds the new run at the top level and the
first run, unchanged, under `first_run`. `reports/metrics_first_run.json` is the first
run's file, byte for byte, and the evaluation copies it into `first_run`.

The new run still does not pass the failure bar. Unusual precision rose from 0.0136 to
0.4589 (95% interval 0.4263 to 0.4916), still below 0.50. Unusual recall fell from
1.0 to 0.835 (0.8004 to 0.8677), because the very-large rule no longer fires on almost
every charge. Wrong unusual flags fell from 187.17 to 2.535 per statement. The unusual
F1 difference from the baseline is now above zero (0.4342 to 0.499). Recurring and
duplicate precision are unchanged, since this change does not touch those rules. Wrong
flags across all types are 8.87 per statement, still above 5. Duplicates alone give
5.45 of them.

The run described in this section is commit `7852a68`. Its `reports/metrics.json` is
kept, byte for byte, as `reports/metrics_adr0006_run.json`, so the numbers above can
still be checked after later runs.

### 2026-09-26: habit test in the duplicate rule

What changed: a close pair of charges is no longer flagged as a possible duplicate when
the same merchant key and exact amount appear on three or more different dates in the
statement. Before, the pair was skipped only when there were three or more close pairs.
[ADR 0007](decisions/0007-habit-test-for-duplicates.md) gives the diagnosis and the
reasons. In short, almost every wrong duplicate flag was two charges of a usual coffee
order at a fixed menu price.

What did not change: the generator, the matching, the metrics, the baselines and the
failure bar. In `src/second_look/thresholds.py`, `DUPLICATE_HABIT_DATES = 3` replaces
`DUPLICATE_HABIT_PAIRS = 3`. No other number changed.

How it was chosen: on the tuning seeds (`0` to `99`) only. The test seeds were then run
once more.

Where the results are: `reports/metrics.json` holds the new run at the top level. The
first run is still under `first_run`, unchanged.

Results on the test seeds: duplicate precision rose from 0.1577 to 0.9808 (95% interval
0.9563 to 1.0). Duplicate recall is unchanged at 0.9903 (0.9752 to 1.0). Wrong duplicate
flags fell from 5.45 to 0.02 per statement. Wrong flags across all types fell from 8.87
to 3.44 per statement, now below 5. The failure bar still fails on two checks, which this
change does not touch: recurring precision 0.861, below 0.90, and unusual precision
0.4589, below 0.50. The new habit test also misses real double charges at a price the
person pays often. The generator never plants those, so this run cannot measure that
loss. ADR 0007 explains it.

### 2026-09-26: correcting this plan's wording on the demo statement and the `--dump` flag

What changed: nothing in the generator, the engine, the thresholds, the matching or the
metrics. This entry corrects two claims this plan made about its own build, found while
writing the README and docs task. Both claims were about how the project would be built,
not about a detection rule or a reported number, so neither `reports/metrics.json` nor
the failure bar depends on either one.

- "The synthetic statement generator" section above, and the "Demo" row of the seeds
  table below, say the demo statement is generator output at seed `9000`. That was never
  built. The committed demo fixture,
  `tests/fixtures/synthetic_demo_statement.csv`, is a short file written by hand for
  `make demo`, not generator output. It holds a real, recognizable merchant name,
  `NETFLIX.COM`, in an invented statement; ADR 0005 allows this, because the row itself
  carries no real person's data. [DATASHEET.md](../DATASHEET.md) already says the
  fixture is hand-written, and the README and `docs/tutorial.md` describe it the same
  way, not as seed `9000`.
- The same section says an optional `--dump DIR` command-line flag writes the
  generator's CSV text and answer key to a folder. No such flag was built.
  `generate_statement()` in `evaluation/generator.py` takes a `dump_dir` argument only;
  there is no command-line flag for it, and `docs/reference.md` and `DATASHEET.md`
  describe it that way.

Where the results are: unchanged. This entry changes no file except this one; it
corrects wording only, in the open, rather than leaving it silently wrong, following the
rule at the top of this plan.
