# 0007: Habit test for duplicate charges

Date: 2026-09-26. Status: accepted. Replaces one part of
[ADR 0002](0002-detection-rules-and-thresholds.md): the habit exception in the
duplicate rule, which counted close pairs (`DUPLICATE_HABIT_PAIRS = 3`). Everything else
in ADR 0002 stays as written.

## Context

ADR 0002 flags two charges as a possible duplicate when they have the same merchant
key, exactly the same amount, and dates no more than `DUPLICATE_WINDOW_DAYS = 2` days
apart. A pair is skipped when a refund of the same amount follows, or when the same
merchant and amount form close pairs like this three or more times in the statement.
That last test is the habit exception. It was meant for charges such as a transit fare
paid twice a day.

The first test run of the synthetic evaluation (commit `f532add`, see
`docs/eval_plan.md`) found almost every planted duplicate, but most of its duplicate
flags were wrong. [Precision](../glossary.md#precision) was 0.1577, and the engine
raised 5.45 wrong duplicate flags per statement on average. The fix in
[ADR 0006](0006-typical-charge-for-simple-unusual-rules.md) did not touch this rule, so
these numbers stayed the same after it.

To find the cause, the rule was instrumented for one run on the tuning seeds (`0` to
`99`). The instrumentation was removed afterwards. It showed:

- Almost every wrong flag was a pair of coffee charges at one of the three coffee shops
  in the generator, at one of its four fixed menu prices ($2.45 to $5.95). There was
  one other wrong flag: two fuel charges that had the same amount by chance.
- No wrong flag touched a planted recurring series or a refunded duplicate. The
  recurring exclusion and the refund exception worked as designed.
- The code matched ADR 0002. For each merchant key and exact amount, it counted the
  close pairs and skipped them all at three or more.
- The flagged coffee prices were paid many times in each statement at the same shop.
  Only one or two of those repeats fell within two days of each other, so the count of
  close pairs stayed below three.

So the fault is in the design, not the code. Counting close pairs asks how often a
habit happens to land within two days. It does not ask whether the price is a habit.
Someone who buys the same coffee every week or so pays that price all year, but only
now and then on two days in a row. Real statements have this pattern too, for example
a usual lunch order or a parking fee. The decoy list in `docs/eval_plan.md` said the
coffee menu would test the habit exception. The test showed the exception was too
narrow.

## Options

1. Lower `DUPLICATE_HABIT_PAIRS`. At one pair it skips every pair, so the rule never
   fires. At two it still misses a usual order that lands close together only once.
2. Shorten the window to the same day. This does not touch the cause, since the same
   coffee can be bought twice in one day. It would also miss real double charges that
   post a day later.
3. Count the different dates on which the same merchant key and exact amount appear
   in the statement, and skip the pair when there are enough of them. A double charge
   repeats one purchase, so its amount shows up on one or two dates. A price that shows
   up on other dates as well is a price the person pays often.
4. Skip whole kinds of merchants, such as coffee shops and transit. A bank export has
   no reliable category column, and a fixed list of merchant types would not carry
   over to other statements.

## Decision

Option 3. `DUPLICATE_HABIT_PAIRS` is replaced by `DUPLICATE_HABIT_DATES = 3`. A close
pair is not flagged when the same merchant key and exact amount appear on three or
more different dates in the statement. Charges that belong to a recurring series still
do not count, as in ADR 0002.

Why three: the pair itself covers one date (both charges on one day) or two dates (the
charge and its copy a day or two later). A third date is the smallest count that shows
the price on an occasion of its own. Several charges of one amount on a single day are
still flagged, because that is one date, not a habit.

Everything else in the rule stays: the two-day window, the exact amount, the refund
exception with its `14` day look-ahead, and the recurring exclusion. The reason string
does not change.

The idea came from the failed test run. Following the freeze rule in
`docs/eval_plan.md`, the choice was checked on the tuning seeds only. Counts of three,
four, five and six dates were compared there. Each found the same planted duplicates,
and each count above three let more coffee pairs through. The test seeds were run once
more after the choice was made, and `docs/eval_plan.md` records the change as a
deviation.

## Consequences

- Two close charges of a price the person pays often are no longer called a possible
  double charge. This is the main source of wrong duplicate flags in the first run.
- A real double charge at a place where the person often pays the same price is now
  missed. Examples are a usual coffee order or a fixed parking fee. The generator never
  plants a duplicate like this: it copies only grocery, restaurant, fuel, shopping,
  pharmacy and entertainment charges, whose amounts are drawn to the cent and rarely
  repeat. So the synthetic [recall](../glossary.md#recall) cannot show this loss, and
  it overstates recall for fixed-price merchants.
- In a short statement, a habit may show up on only two dates, and a close pair of it
  is still flagged.
- The instrumentation also showed one planted duplicate that the engine skips on
  purpose. The generator refunds some ordinary shopping charges. When it refunds the
  original of a planted duplicate, the refund exception applies, but the answer key
  still counts the pair as an unrefunded duplicate. This is a gap in the generator's
  labels, not in the rule. It is left as it is, so the generator and the matching stay
  as the evaluation plan froze them.
- The same person wrote the generator, the rules and this fix, and chose the fix after
  seeing a failed test result. A good synthetic score after this change says little
  about real statements.
