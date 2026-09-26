# 0002: Detection rules and thresholds

Date: 2026-09-25. Status: accepted. The "median of all charges in the statement" in the
two simple unusual-transaction rules is replaced by
[ADR 0006](0006-typical-charge-for-simple-unusual-rules.md) (2026-09-26). The habit
exception in the duplicate rule is replaced by
[ADR 0007](0007-habit-test-for-duplicates.md) (2026-09-26).

## Context

The engine raises four kinds of flag: recurring charges, price increases on them,
possible duplicate charges, and unusual transactions. Each rule needs a number that
decides when it fires. This record fixes every number before any code or evaluation
exists, and gives the reason for each one. The reasons are judgment calls about how
bank charges usually look. They are not measured facts. The synthetic evaluation in
`docs/eval_plan.md` will test them, and `docs/whats_weak.md` will say how far that
test can go.

If the evaluation task changes a number, it must record the change as a deviation in
`docs/eval_plan.md`. Any tuning must use separate tuning seeds, never the seeds that
produce the reported results.

Terms used below:

- A charge is money leaving the account. The importer ([ADR 0003](0003-importing-statements.md))
  turns every row into an amount where a charge is positive and money coming in (a
  refund or a deposit) is negative.
- The statement end is the last date in the file. It stands in for "today"
  ([ADR 0001](0001-one-engine-two-doors.md)).
- The median absolute deviation (MAD) is the median distance of the values from their
  median. It measures spread, and one extreme value barely moves it.

## Options

For recurring charges:

1. Group by a cleaned merchant name, then by a close amount, then check the spacing of
   the dates. Every step can be explained in one sentence.
2. Fuzzy name matching (edit distance) across merchants. It catches more spelling
   changes, but it also merges different merchants, such as a store and its
   subscription service, and each false merge makes a false recurring charge.

For unusual transactions:

1. Median-based z-scores (the [modified z-score](../glossary.md#modified-z-score) of
   Iglewicz and Hoaglin), plus a few simple rules. One large value does not hide itself
   by stretching the spread.
2. Ordinary z-scores with the mean and standard deviation. One large charge inflates
   the standard deviation, which makes that same charge look less unusual.
3. A trained model, such as an isolation forest. There are no labels for real
   statements, and a score from a model is harder to turn into a plain reason.

## Decision

Option 1 in both lists. The rules and numbers follow. Every number below becomes a
named constant in one module, `src/second_look/thresholds.py`, so the code, this
record and `docs/reference.md` can be checked against each other.

### Merchant names

The merchant key is built from the description in fixed steps, in this order:

1. Unicode NFKC normalising, then upper case.
2. Remove a known payment-processor prefix at the start: `SQ *`, `TST*`, `PAYPAL *`
   and `PP*`. The list is short on purpose and lives in code.
3. Remove store numbers and reference numbers: any `#` followed by digits, and any run
   of four or more digits.
4. Replace punctuation with a space, except `&` and `'`, then collapse spaces.
5. Remove a Canadian province or territory code (such as `ON` or `QC`) when it is the
   last word.
6. Remove a legal suffix when it is the last word: `INC`, `LTD`, `LLC`, `CORP`.

If these steps leave nothing, the key is the upper-case description with spaces
collapsed. The key is only for grouping. The page and the command line show the
original description next to every flag, so the user can see which rows were grouped.

### Recurring charges

A recurring charge is a series of charges at one merchant key, with close amounts, at
a regular spacing.

- Close amounts: two charges have the same amount when they differ by no more than the
  larger of `SAME_AMOUNT_ABS = 0.05` dollars and `SAME_AMOUNT_REL = 0.03` (three
  percent) of the smaller one. Within a merchant, charges are taken in date order.
  Each one joins the existing group whose median amount is closest and within that
  tolerance, or it starts a new group. The five cent floor covers tax rounding on small
  charges. The three percent covers small exchange-rate moves on subscriptions billed
  in another currency. It is meant to stay below most price rises, which are then
  caught by the price increase rule instead of being hidden.
- Spacing: the gaps in days between charges in a group decide the period.

| Period | Gap window in days | Charges needed | Charges in a year |
|---|---|---|---|
| Weekly | `6` to `8` | `4` | `52` |
| Monthly | `25` to `35` | `3` | `12` |
| Yearly | `358` to `372` | `2` | `1` |

- Why these windows: a monthly charge set for the last day of a month lands on a shorter date in February, and
  a weekend or holiday can push a posting a few days later. Weekly and yearly windows
  allow the same few days of posting delay.
- Why these counts: two charges a month apart can be chance, such as two grocery trips,
  so a monthly series needs three charges (two matching gaps). A weekly series needs
  four, about one month. A yearly series can only show two charges in a statement
  shorter than three years, so two are allowed, and the flag says "seen twice, a year
  apart" so the user can judge.
- A group is regular when every gap is inside the window. For weekly and monthly
  series, one gap of about two periods (twice the window bounds) is also allowed, so
  one skipped charge does not hide a subscription.
- A series is active when its last charge is no more than `1.5` periods before the
  statement end (using `7`, `30` and `365` days as the period length). Otherwise it is
  listed as "seems to have stopped".
- Yearly cost is the latest charge amount times the charges in a year from the table
  (`52`, `12` or `1`). It is shown only for active series and is rounded to the cent.
  It is a projection at today's price, not what the user paid over the past year. The
  weekly factor is `52`, not `365.25 / 7`, because it is the number a reader would use.

### Price increases

A price increase joins an old series and the charges that follow it:

- The old series is a recurring charge as defined above.
- After its last charge, the same merchant key has new charges at the same spacing (the
  first one inside the period's gap window). The new charges have the same amount as
  each other, and that amount is higher than the old one by more than the close-amount
  tolerance.
- The new price must hold for `PRICE_RISE_MIN_NEW = 2` charges for weekly and monthly
  series. One higher charge can be a one-time extra purchase at the same place. For
  yearly series one new charge is enough, because waiting for a second one means
  waiting another year, and the old series already showed the date pattern.
- The flag shows the old amount, the new amount, the change in percent (whole number)
  and the change in yearly cost at the new price.
- The old series and the new charges then count as one recurring charge. It is listed
  once, at the new price, and the old part is not listed as stopped.
- Price drops are not flagged. They are not worth a second look.

### Duplicate charges

Two charges form a possible duplicate when all of these hold:

- the same merchant key
- exactly the same amount, to the cent (a double charge repeats the same amount; two
  different amounts on one day are usually two real purchases)
- dates no more than `DUPLICATE_WINDOW_DAYS = 2` days apart (a double charge usually
  posts the same day or the next business day, and a weekend can add a day)

A pair is not flagged when:

- A refund of the same amount from the same merchant key follows within
  `REFUND_LOOKAHEAD_DAYS = 14` days. The problem has already been fixed.
- The same merchant and amount form close pairs like this `DUPLICATE_HABIT_PAIRS = 3` or
  more times in the statement. That pattern looks like a habit, such as a transit fare
  paid twice a day, not a billing error.

### Unusual transactions

These tests run only on charges that are not part of a recurring series. Recurring
charges are covered by the price increase rule.

No unusual-transaction flag fires until the statement covers at least
`MIN_STATEMENT_DAYS = 60` days and holds at least `MIN_STATEMENT_CHARGES = 30`
charges. "Unusual for you" needs a record of what is usual.

Modified z-score:

- The score works on the natural log of the amount. Spending is skewed: a few large
  charges and many small ones. On the log scale, "three times more" means the same
  thing at every price level, and the reason string can say `3.0 times your usual`.
- For a charge with log amount `x`, and a comparison group of other charges with median
  `m`, the score is `(x - m) / s`, where `s = max(1.4826 * MAD, MIN_LOG_SCALE)`. The
  factor `1.4826` makes the MAD match the standard deviation for normal data.
  `MIN_LOG_SCALE = 0.1` stops a group whose amounts are almost all the same from making
  a small change look extreme.
- The charge itself is left out of its comparison group.
- A score above `Z_THRESHOLD = 3.5` counts. This is the cut-off that Iglewicz and
  Hoaglin recommend for the modified z-score, as described in the
  [NIST/SEMATECH e-Handbook](https://www.itl.nist.gov/div898/handbook/eda/section3/eda35h.htm).
  Only high amounts count. Spending less than usual is not worth a second look.

The score is computed against two groups:

- Per merchant: the other non-recurring charges at the same merchant key. It needs at
  least `MIN_MERCHANT_HISTORY = 5` of them. A median and MAD from fewer values move too
  much when one value changes.
- Per category: the other non-recurring charges with the same category. It needs at
  least `MIN_CATEGORY_HISTORY = 10` of them, because a category mixes more kinds of
  purchase than one merchant does. This test runs only when the statement has a
  category column and the user mapped it. The engine does not guess categories from
  merchant names.

A high score also needs two more conditions. The amount must be at least
`UNUSUAL_MIN_RATIO = 2` times the group median, so the flag is large enough to notice.
It must also be at least `UNUSUAL_MIN_AMOUNT = 25` dollars, so small odd charges do
not fill the list. The score says the charge is rare for this user. The ratio says it
is large. The dollar floor says it costs enough to check.

Simple rules, for the cases where the score has too little history:

- New merchant, large amount: this is the first charge at a merchant key, at least
  `NEW_MERCHANT_MIN_DAYS = 60` days of statement come before it, and the amount is at
  least `NEW_MERCHANT_RATIO = 3` times the median of all charges in the statement and
  at least `UNUSUAL_MIN_AMOUNT` dollars. Without the days rule, every merchant in the
  first weeks would look new.
- Very large charge: the amount is at least `LARGE_CHARGE_RATIO = 10` times the median
  of all charges in the statement, and at least `UNUSUAL_MIN_AMOUNT` dollars. Planned
  large purchases will trigger it, and the user can dismiss them.

When several of these fire on one charge, the charge gets one flag that lists every
reason.

### Reason strings

Every flag carries a reason: one or two short sentences in plain English. The pattern
is always the facts first (amount, merchant, date), then the comparison that made it
fire, with the number that crossed the line. Money shows as dollars with two decimals.
Ratios show one decimal. Percentages are whole numbers. Dates are `YYYY-MM-DD`, which
cannot be misread as day-first or month-first. The section title on every screen is
"Worth a second look".

The patterns, with `{}` marking the filled-in values:

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

The wording rules for these strings, and the words they must never use, are in
[ADR 0005](0005-privacy-and-wording.md). A reason never guesses at why a charge
happened and never blames anyone.

## Consequences

- Every flag can be traced to one rule and one number, which makes errors easy to
  explain in the error analysis.
- The unusual-transaction flags depend on a category column that many bank exports may
  not have. Without it, only the per-merchant score and the two simple rules run.
- A yearly price increase needs two old yearly charges and one new one, so in practice
  about three years of history. Most users will not export that much.
- A subscription billed in another currency whose price drifts more than three percent
  and stays there will look like a price increase. The flag shows both amounts, so the
  user can see it.
- Merchants whose descriptions change a lot from charge to charge (for example a new
  reference word each time) will not group, and their recurring charges will be missed.
- Every period other than weekly, monthly and yearly (for example every two weeks or
  every three months) is missed in this version.
- The processor-prefix list, the category rule and every number here are assumptions.
  The synthetic generator is written by the same person, so a good synthetic score
  cannot show these assumptions hold on real statements.

## Option not taken

Fuzzy merchant matching was not chosen, because a false merge creates a false
recurring charge, and exact keys after fixed cleaning steps are easier to explain.
