# 0006: Typical charge for the simple unusual rules

Date: 2026-09-26. Status: accepted. Replaces one part of
[ADR 0002](0002-detection-rules-and-thresholds.md): the "median of all charges in the
statement" used by the new-merchant rule and the very-large rule. Everything else in
ADR 0002 stays as written.

## Context

ADR 0002 has two simple rules for unusual transactions. The new-merchant rule fires on
a first charge at a merchant that is at least `NEW_MERCHANT_RATIO = 3` times the median
of all charges in the statement. The very-large rule fires on a charge that is at least
`LARGE_CHARGE_RATIO = 10` times that same median. Both also need at least
`UNUSUAL_MIN_AMOUNT = 25` dollars.

The first test run of the synthetic evaluation (commit `f532add`, see
`docs/eval_plan.md`) found every planted unusual charge, but its unusual flags were
almost all wrong. [Precision](../glossary.md#precision) was 0.0136, and the engine raised 187.17 wrong unusual
flags per statement on average.

To find the cause, the rules were instrumented for one run on the test seeds and on
the tuning seeds. The instrumentation was removed afterwards. It showed:

- Almost every wrong flag came from the very-large rule firing on its own. Most of the
  rest came from the new-merchant rule. The per-merchant and per-category scores caused
  only a small share.
- The code matched ADR 0002. The scores used the right groups (other charges at the
  same merchant, other charges in the same category), the right minimum history, and
  left the charge out of its own group. The simple rules used the median of all
  charges, as ADR 0002 says.
- The median of all charges was the price of a transit fare or a coffee. The generator
  plants a transit fare of $3.35 on most weekdays, and coffee at fixed menu prices from
  $2.45 to $5.95. These frequent charges are more than half of all charges, so they set
  the median. Ten times a few dollars is below an ordinary grocery bill, so almost every
  grocery, fuel and shopping charge was called "10 times your typical charge".

So the fault is in the design, not the code. A median over all charges counts a habit
once per purchase. Someone who buys a transit fare every workday has a "typical charge"
of a few dollars, even though most of their money goes on larger charges. Real
statements have this pattern too.
`docs/eval_plan.md` predicted this failure before the first run.

## Options

1. Keep the median of all charges and raise `LARGE_CHARGE_RATIO` and
   `NEW_MERCHANT_RATIO`. This changes the numbers, not the cause. The right ratio would
   then depend on how many small habits a person has.
2. The median, over merchants, of each merchant's median charge, so each merchant
   counts once. On the tuning seeds this removed most wrong flags. It failed on
   statements with a subscription whose description carries a new reference word each
   month. ADR 0002 already says such charges do not group, so one subscription became
   one merchant key per charge. Those keys outvoted every other merchant and pulled
   the typical charge back down to the subscription price.
3. The median of the distinct charge amounts. Each amount counts once, however often
   it is repeated. A fare paid hundreds of times is one value. A subscription that
   splits into many merchant keys still has one price, so it is also one value.
4. A trained model or a percentile of a spending-weighted distribution. These are
   harder to explain in one reason sentence, and ADR 0002 already turned down a
   trained model for that reason.

## Decision

Option 3. The typical charge is the median of the distinct amounts of all charges in
the statement. Recurring charges still count, as in ADR 0002. The charge being judged
is left out, which matches how ADR 0002 treats the score: its amount is dropped from
the set when no other charge has the same amount. Without this, a statement where
almost every charge has one amount would count the large charge as half of the
"typical" values.

The ratios and the dollar floor do not change. The reason strings do not change: they
still say "{ratio} times your typical charge ({median})".

The same change fixes one small gap between the code and ADR 0002. ADR 0002 says the
new-merchant rule fires on the first charge at a merchant key. The code only looked at
charges outside recurring series. A one-off charge at a merchant that already had a
subscription could then be called "your first charge" there. The code now counts every
charge when it decides which one is first.

The idea came from the failed test run. Following the freeze rule in
`docs/eval_plan.md`, the options above were compared on the tuning seeds only. The test
seeds were run once more after the choice was made, and `docs/eval_plan.md` records the
change as a deviation.

## Consequences

- The simple rules now compare a charge with the size of a typical purchase, not the
  size of the most frequent purchase.
- The fix works best when frequent small charges repeat the same amount. The generator
  plants exactly that: fixed transit fares and a fixed coffee menu. In real statements,
  frequent small charges can vary in price (ride-hailing, a different coffee order each
  day). Each of those is a distinct amount, so they can still pull the typical charge
  down. The synthetic result is likely better than what a real statement would show.
- One large set of repeated amounts no longer moves the typical charge. A person whose
  charges are nearly all small and all different will still get a low typical charge.
- On the tuning seeds, most remaining wrong unusual flags come from the per-merchant
  score. With five to a
  dozen past charges at one merchant, the median absolute deviation can come out much
  smaller than the real spread, so an ordinary charge two or three times the usual
  amount can score above `Z_THRESHOLD = 3.5`. That is a separate problem, left for a
  later task. This record does not change `MIN_MERCHANT_HISTORY` or `Z_THRESHOLD`.
- The same person wrote the generator, the rules and this fix, and chose the fix after
  seeing a failed test result. A good synthetic score after this change says little
  about real statements.
