# What's weak

The full list of known limits. The README shows the top few. They are ranked by how
much each one would change the tool's usefulness on real statements if it were left
alone, with the largest first. Each one says what was done about it, even when the
answer is "nothing yet".

The numbers come from `reports/metrics.json` and `reports/error_analysis.json`. The
causes are explained in [reports/error_analysis.md](../reports/error_analysis.md).

## Ranked list

| Rank | Weakness | What was done |
|---|---|---|
| 1 | Tested on synthetic statements only | Said next to every result. The local feedback export is the only path to real evidence |
| 2 | Unusual-charge [precision](glossary.md#precision) is below its own bar | One fix (ADR 0006). The main remaining cause is found but not fixed |
| 3 | Recurring-charge precision is below its own bar | Cause found. Nothing changed yet |
| 4 | Some real recurring patterns are missed by design | Written in ADR 0002. Nothing changed |
| 5 | Unusual charges without a category column | Nothing. Depends on the bank's export |
| 6 | Real double charges at a price paid often are skipped | Accepted in ADR 0007 as the cost of the fix |
| 7 | A one-off extra charge hides a price increase | Cause found. Nothing changed yet |
| 8 | The fixes were chosen after seeing the failed test run | Choices made on the tuning seeds only. The comparisons are not committed |
| 9 | Web page limits: one browser tested, Content-Security-Policy gaps | Written in ADR 0004 |
| 10 | No confirmed bank presets | Each bank's own help pages checked. None found |

## 1. Tested on synthetic statements only

Every number in this repo comes from statements that our own script made, with
events that the same script planted. The test shows whether the rules find what was
planted. It cannot show how well the tool works on real bank statements. Real
statements have merchant names, posting delays, price changes and spending habits that
the generator does not copy. [docs/eval_plan.md](eval_plan.md) says this before any
number.

The same person wrote the rules, the generator and both fixes. The generator's
choices were made by someone who knew what the rules look for. So even a good
synthetic score may partly reflect a generator that fits the rules.

The stress set gives a hint of how much this matters. With a little more posting
delay, currency noise and changing descriptions, recurring [recall](glossary.md#recall)
falls from 0.9588 to 0.5959.

What was done: the caveat is in the eval plan and will sit next to the headline in
the README. The web page has a local feedback export
([ADR 0005](decisions/0005-privacy-and-wording.md)). It is the only way to learn about
real statements, and it depends on users choosing to share a file, so it will be
rare. No real-world result exists yet.

## 2. Unusual-charge precision is below its own bar

The bar set before any result was 0.50. Unusual precision is 0.4589, so more than
half of the unusual flags are wrong on synthetic data. This is after a real fix:
[ADR 0006](decisions/0006-typical-charge-for-simple-unusual-rules.md) raised it from
0.0136.

Of the 507 wrong unusual flags, 442 involve the per-merchant score. That score
compares a charge with only five to a few dozen past charges at the same shop. Its
estimate of the usual spread is then unsteady, and ordinary charges two to five times
the usual amount get flagged. The same test also misses planted charges three to five
times the usual amount: it found 44 of them and missed 48.

On real statements this is likely worse, not better. ADR 0006 notes that its fix
works best when frequent small charges repeat one price, as the generator's transit
fares and coffee menu do. Real small charges vary more.

What was done: ADR 0006 fixed the two simple rules. The per-merchant score was not
changed. The error analysis suggests a better spread estimate for short histories,
not a different cut-off. Any change must be tuned on the tuning seeds.

## 3. Recurring-charge precision is below its own bar

The bar was 0.90. Recurring precision is 0.861, unchanged since the first run. This
is the feature the tool leads with, and each wrong recurring flag also adds a yearly
cost that is not real.

Of the 177 wrong recurring flags, 109 are two ordinary shop charges about a year apart
at nearly the same amount. ADR 0002 accepts a yearly series from two charges, because a
statement shorter than three years cannot show more. Among hundreds of grocery and
restaurant charges, some pairs land a year apart by chance. The flag says "charged
twice, a year apart", so the user can judge, but it still counts as wrong.

What was done: nothing yet. The cause is in the error analysis. A fix could ask more
of a two-charge yearly series, but it could also lose some real yearly subscriptions,
so it must be weighed on the tuning seeds.

## 4. Some real recurring patterns are missed by design

[ADR 0002](decisions/0002-detection-rules-and-thresholds.md) looks only for weekly,
monthly and yearly series with amounts within three percent. It misses:

- bills whose amount changes each month, such as electricity: the engine found 3 of
  the 200 planted varying bills (recall 0.015)
- subscriptions whose description changes each time with a new code: 0 of 47 found
- series every two weeks, every three months or every six months: the generator does
  not plant them, so the test cannot count the loss

These misses are silent. A user sees a clean list and may think nothing else repeats.

What was done: ADR 0002 and the eval plan state these limits. Nothing changed.

## 5. Unusual charges without a category column

The per-category test runs only when the export has a category column and the user maps
it. Many bank exports may not have one. On synthetic chequing statements, which have
no category column, the engine found 0.6994 of the planted spikes. On credit card
statements, which have one, it found 0.7975.

What was done: nothing. The engine does not guess categories from merchant names, on
purpose (ADR 0002).

## 6. Real double charges at a price paid often are skipped

[ADR 0007](decisions/0007-habit-test-for-duplicates.md) fixed most wrong duplicate
flags with a habit test. A close pair is skipped when the same shop and exact amount
appear on three or more dates. The cost is real. A true double charge at a place where
the person often pays the same price is now missed. Examples are a usual coffee order
or a fixed parking fee.

The generator never plants that kind of duplicate. So the synthetic duplicate recall
overstates recall at fixed-price shops, and this run cannot measure the loss. Such
charges are often small, which limits the harm.

What was done: accepted in ADR 0007 as the price of the fix.

## 7. A one-off extra charge hides a price increase

All 14 missed price increases (of 206 planted) have one cause. A one-off extra charge
at the same subscription came before the new price. The engine tries to join a series
only with the next amount group at that merchant, and the extra charge makes a group
in between. The old and new prices are then listed as two separate recurring charges,
and the price increase is never reported.

What was done: nothing yet. The error analysis names the code path. The price increase
detector still passes its bar.

## 8. The fixes were chosen after seeing the failed test run

The eval plan allows tuning only on the tuning seeds (`0` to `99`), never on the test
seeds (`1000` to `1199`). Both fixes followed that rule for the choices they made:

- ADR 0006 compared its options on the tuning seeds only.
- ADR 0007 compared counts of three to six dates on the tuning seeds only, and picked
  `DUPLICATE_HABIT_DATES = 3` there.

This is a strength. No threshold or option was picked by comparing test-seed scores.

Two limits remain. Both fixes began because the first test run failed, so the test
seeds decided which problems got fixed. ADR 0006 also looked inside the engine's flags
on the test seeds, as well as the tuning seeds, to find the cause. And the tuning-seed
comparisons were run by hand and are not committed. The fix commits hold only the
engine change and its tests, so a reader must take the ADRs' word for those
comparisons.

What was done: every change is recorded as a dated deviation in the eval plan, and the
first run stays in `reports/metrics.json` unchanged.

## 9. Web page limits

From [ADR 0004](decisions/0004-web-door-pyodide-and-csp.md):

- The browser test in CI runs in Chromium only. Firefox and Safari are not tested.
- The page sets its Content-Security-Policy in a `<meta>` tag, which cannot stop
  another site from showing the page in a frame.
- The policy allows requests to the site's own address. The browser test and the short
  code cover this, not the policy.
- Browser extensions the user installed run outside the policy.

Also, CI runs the Python tests on Python `3.11` only. The core must also run on the
Python `3.14` inside Pyodide. Only the browser test, on the demo statement, checks that.

What was done: the limits are written down. Nothing else yet.

## 10. No confirmed bank presets

There is no preset for RBC, TD, CIBC, BMO or Scotiabank. So every user maps the
columns by hand, even for a common bank.
[ADR 0003](decisions/0003-importing-statements.md) allows a preset only from the
bank's own help page or a real header row from Iliya. A search of each bank's own
help and support pages on 2026-09-26 found none that lists the exact CSV header names.

This costs one setup step. It changes no detection rule and no result, which is why it
ranks last.

What was done: each bank's own site was checked, not third-party pages. The "Bank CSV
presets" section in [docs/reference.md](reference.md) lists what was and was not found.
A preset for any of the five would help.
