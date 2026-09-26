# Error analysis

This page looks at every wrong flag and every missed event in the current evaluation
run. It asks which planted events each detector misses or flags wrongly, and why.

The run is the one in `reports/metrics.json`: `200` synthetic test statements (seeds
`1000` to `1199`), after the fixes in
[ADR 0006](../docs/decisions/0006-typical-charge-for-simple-unusual-rules.md) and
[ADR 0007](../docs/decisions/0007-habit-test-for-duplicates.md). The counts by cause
come from `reports/error_analysis.json`, which `make error-analysis` writes. That
script reruns the engine on the same seeds and uses the same matching code as the
evaluation. It changes no rule, threshold or seed.

Every statement here is synthetic. These causes explain the rules on data from our
own generator. They say little about how often each cause happens on real bank
statements. [docs/eval_plan.md](../docs/eval_plan.md) explains this limit.

## In plain words

Two of the four detectors are still below the bar that was set before any result.

- Recurring charges: most wrong flags are two ordinary shop visits that happen to be
  about a year apart, at almost the same amount. The rule accepts a yearly charge
  after only two charges, so it cannot tell these apart from a yearly subscription.
- Unusual charges: most wrong flags come from comparing a charge with a short history
  at one shop. The same test also misses many planted charges that are only three to
  five times the usual amount.

The duplicate and price increase detectors pass. Every missed price increase has the
same cause, and that cause also makes some wrong recurring flags.

## Summary

| Flag type | [Precision](../docs/glossary.md#precision) (bar) | [Recall](../docs/glossary.md#recall) (bar) | Wrong flags | Misses | Main cause |
|---|---|---|---|---|---|
| Recurring | 0.861 (0.90), below | 0.9588 (0.90) | 177 | 47 | Two charges a year apart at an ordinary shop |
| Price increase | 1.0 (0.80) | 0.932 (0.80) | 0 | 14 | A one-off extra charge before the new price |
| Duplicate | 0.9808 (0.50) | 0.9903 (0.80) | 4 | 2 | Generator label gap (misses), chance pairs (wrong flags) |
| Unusual | 0.4589 (0.50), below | 0.835 (0.50) | 507 | 85 | The per-merchant score on a short history |

Wrong flags and misses are totals over the `200` statements. Precision and recall are
point values from `reports/metrics.json`. Their 95% intervals are there too.

## Recurring charges: below the bar on precision

### Wrong flags

The detector raised 177 wrong recurring flags. The script sorts each one by what its
charges really were in the answer key.

| What the flag covered | Period the engine gave | Wrong flags |
|---|---|---|
| Two ordinary charges at one shop, about a year apart | yearly | 109 |
| Three or more ordinary charges at one shop, about a month apart | monthly | 23 |
| Part of the varying monthly bill | monthly or yearly | 31 |
| The new-price part of a subscription whose price went up | monthly or weekly | 14 |

Two-charge yearly flags on ordinary spending are the largest group, 109 of the 177.
[ADR 0002](../docs/decisions/0002-detection-rules-and-thresholds.md) allows a yearly
series from two charges, `358` to `372` days apart, whose amounts are within the
close-amount tolerance (the larger of five cents and three percent). A statement of
more than a year holds hundreds of grocery and restaurant charges. By chance, two of
them at the same shop can land about a year apart at nearly the same amount. The rule
has no way to tell that pair from a yearly subscription. Among ordinary shops,
groceries (53) and restaurants (31) give the most wrong flags, counted over every
period. People visit them often, and their amounts vary, so close pairs happen by
chance.

This is a design limit in ADR 0002, not a code bug. ADR 0002 chose two charges on
purpose, because a statement shorter than three years can only show two charges of a
yearly subscription. Its reason string says "charged twice, a year apart" so the user
can judge. The cost shows up here as the largest single source of wrong flags.

The 23 monthly flags are the same effect at a shorter period. Three visits to one shop
fell about a month apart with amounts within three percent. In 19 of them the amounts
were close but not equal.

The 31 flags on the varying bill need a note. The eval plan does not expect the
engine to catch this bill, because its amount moves by more than three percent from
month to month. When three of its
charges happen to fall within three percent of each other, the engine flags that
part. The matching rule counts a flag as wrong when it covers less than half of the
bill's charges. So these flags are wrong by the rule set in advance, but each one points at a
real recurring bill.

The last 14 are explained under price increases below.

### Misses

The detector missed 47 fixed-amount series. All 47 are subscriptions whose
description ends with a new three-letter code each time. ADR 0002 says these will not
group, and the eval plan kept them in the recall count on purpose. The engine found
every one of the other 1093 fixed series.

### Quality of the hits

Among the 1093 hits, the period was always right. The active or stopped status was
wrong for 11. The secondary check "right yearly cost" in `metrics.json` reads 0.8783,
which looks like one cost in eight is wrong. It is not. That share divides by all
1093 hits, and 122 of them are stopped series, which have no yearly cost. Every one
of the other 960 hits had the answer key's yearly cost to the cent.

## Price increases: passes

The detector made no wrong price increase flags and missed 14 of the planted
increases. All 14 have one cause. Before the new price began, the generator had
placed a one-off extra charge at the same subscription, above the usual price. This
is a decoy the eval plan adds on purpose.

The engine groups one merchant's charges by amount, in the order each amount first
appears. It then tries to join a series only with the next amount group
(`detect_recurring` in `src/second_look/recurring.py`). The one-off extra charge makes
a group of its own that sits between the old price and the new price. So the old and
new prices are never compared. Both parts are listed as separate recurring charges,
and the new-price part becomes one of the 14 wrong recurring flags above.

The missed increases had between three and 58 charges at the new price, so too few
new charges is not the cause. A later change could try every later amount group at
that merchant, instead of just the next one. Any such change must be checked on the tuning
seeds first, as the eval plan requires.

## Duplicates: passes

There were four wrong duplicate flags. Three are two charges of one coffee price
at one shop. That shop and price appear on fewer than three dates in the statement,
so the habit test from ADR 0007 does not skip the pair. The fourth is two pharmacy
charges with the same amount by chance.

There were two misses. In both, a refund of the same amount at the same shop follows
the pair. ADR 0007 traced this to the generator's ordinary refunds of shopping
charges, which can refund the original of a planted duplicate. The engine's refund
exception then skips the pair, as designed, but the answer key still counts it as an
unrefunded duplicate. ADR 0007 describes this gap in the generator's labels. It was left alone
so the generator stays as the plan froze it.

This run cannot measure the cost ADR 0007 accepted. A real double charge at a price
the person pays often, such as a usual coffee order, is now skipped. The generator
never plants that kind of duplicate.

## Unusual charges: below the bar on precision

### Wrong flags

The detector raised 507 wrong unusual flags. The reason text on each flag names the
test that fired, so the script can sort them.

| Test that fired | Wrong flags |
|---|---|
| Per-merchant score only | 409 |
| Per-merchant and per-category scores | 30 |
| Per-merchant score and the very-large rule | 3 |
| Per-category score only | 33 |
| New-merchant rule only | 32 |

So 442 of the 507 wrong flags involve the per-merchant score. ADR 0006 predicted this
from the tuning seeds.

The per-merchant score compares a charge with the other charges at the same shop. It
needs at least five of them. It divides the distance from the shop's usual amount by
the spread of those past charges. With five to nine past charges, that spread moves
a lot from one statement to the next. When it comes out small, an ordinary charge a
little above the usual amount scores above the cut-off of `3.5`.

The counts support this. Of the 409 flags from the per-merchant score alone:

- 229 had five to nine past charges at that shop, 125 had ten to 19, and 55 had 20 or
  more.
- 183 were two to three times the shop's usual amount, and 164 were three to five
  times. Another 58 were five to ten times, and four were ten times or more.

The generator draws ordinary charges with a wide spread (`sigma` from `0.5` to `0.7`
on the log scale, per the eval plan). With that spread, a charge two or three times
the usual amount is common. It is not a real outlier.

The rate per charge is small, but it adds up. The score ran on 170,769 charges, about
854 per statement. It fired wrongly on 0.26% of them. Across that many charges, even
this small rate gives more than two wrong flags per statement.

By kind of charge, the wrong flags fell on shopping (145), restaurants (125),
groceries (115), pharmacy (57), entertainment (39) and fuel (18). Four more were
one-off extra decoys, and four were planted duplicate copies.

The 32 wrong new-merchant flags are all ordinary shop charges. Each is the first
visit to that shop in the statement, after at least `60` days of history, and at least
three times the typical charge. Of these, 24 were shopping. The rule cannot tell a
shop the person rarely uses from a new one.

### Misses

The detector missed 85 of the 515 planted unusual charges.

- One is a large charge at a new merchant. It was 2.97 times the typical charge,
  just under the rule's ratio of three.
- The other 84 are spikes at a known shop. Every one of them scored at or below `3.5`
  on the per-merchant test. On 52 of them, the statement was a chequing account with
  no category column, so no second test could fire. On the other 32, the category
  score was also at or below `3.5`.

The size of the planted spike matters most. The generator draws the spike factor from
three to ten times the usual amount.

| Planted spike factor | Found | Missed | Recall |
|---|---|---|---|
| 3 to 5 times | 44 | 48 | 0.4783 |
| 5 to 10 times | 203 | 36 | 0.8494 |

Spike recall is 0.6994 on chequing statements, which have no category column, and
0.7975 on credit card statements, which do.

### What this means

The wrong flags sit mostly at two to five times the usual amount. The missed spikes
sit mostly at three to five times. They overlap. This suggests that moving the
cut-off of `3.5` alone would trade one error for the other. A fix would more likely
change how the spread is estimated from a short history. That was not tried here.

## The stress set

The stress set reruns the same seeds with more posting delay, more currency noise,
more changing descriptions and smaller spikes. The eval plan does not judge it
against the bar. It shows how fast the rules break outside their windows:

- recurring recall falls from 0.9588 to 0.5959, and precision from 0.861 to 0.7816
- price increase recall falls from 0.932 to 0.6402
- unusual precision falls from 0.4589 to 0.2703

The main result depends on the generator staying inside the ADR 0002 windows.

## Limits of this analysis

- The causes above come from rules in `evaluation/error_analysis.py`. It names a
  background charge's category by looking up the generator's merchant names, and it
  reads the test that fired from the reason text.
- It explains the rules on synthetic data. It cannot say how common each cause is on
  real statements.
- It reads the engine only. No rule or threshold was changed because of it.
