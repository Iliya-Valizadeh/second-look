# Explanation

Background and reasons. This page says why the project works the way it does. The
tutorial and how-to guides say what to type.

## Why fixed rules, not a trained model

second-look uses named, fixed rules for all four kinds of flag, not a trained model.
[ADR 0002](decisions/0002-detection-rules-and-thresholds.md) explains the choice: there
are no labels for real statements, and a score from a trained model is harder to turn
into a plain reason. A fixed rule can always point at the one number that made it fire.

The four rules:

- Recurring charges group a merchant's charges by a close amount, then check the
  spacing of the dates against a weekly, monthly or yearly window.
- Price increases look for a new, higher, repeated amount right after a recurring
  series ends.
- Duplicate charges look for the same merchant and the same exact amount, close
  together in time, unless a refund follows or the pair looks like a habit.
- Unusual charges use a [modified z-score](glossary.md#modified-z-score), plus two
  simple rules for a first-time or a very large charge. The score compares a charge
  with the [median absolute deviation](decisions/0002-detection-rules-and-thresholds.md#unusual-transactions)
  of a merchant's or a category's other charges, not an ordinary standard deviation.
  ADR 0002 turned ordinary z-scores down for this reason: one very large charge would
  raise the spread and make itself look less unusual, which is the opposite of what
  the tool needs.

Two later fixes changed part of this design after the first evaluation run:

- [ADR 0006](decisions/0006-typical-charge-for-simple-unusual-rules.md) changed what
  "typical charge" means for the two simple unusual-charge rules, after the first run
  called almost every grocery and shopping charge unusual.
- [ADR 0007](decisions/0007-habit-test-for-duplicates.md) changed how the duplicate
  rule tells a real double charge from a price paid often, such as a usual coffee
  order.

`reports/error_analysis.md` and `docs/whats_weak.md` say which of these rules still
raise too many wrong flags on the synthetic tests.

## Privacy and security design

The engine can read a real bank statement, so two decisions shape how that statement
is handled and how the tool talks about it.

[ADR 0004](decisions/0004-web-door-pyodide-and-csp.md) is about the web page (Door 2).
It runs the same `second_look` package inside the browser with
[Pyodide](glossary.md#pyodide), so a statement never has to leave the user's device.
The page's [Content-Security-Policy (CSP)](glossary.md#content-security-policy-csp)
blocks its own code from contacting any address other than the page's own origin, and
a browser test in CI fails the build if any request goes anywhere else. Some limits
stay: a `<meta>` CSP cannot stop another site from framing the page, only Chromium is
tested, and a browser extension the user installed runs outside the page's CSP.

[ADR 0005](decisions/0005-privacy-and-wording.md) is about what the tool says and what
it keeps. The tool never suggests a crime; a flag means a charge matches a pattern, not
that anyone did anything wrong. The web page's feedback file is local-only: a button
builds a JSON file in the browser and hands it to the browser's own download, and by
default the file leaves out merchant names, descriptions, dates and amounts. Sharing
that file afterwards is always the user's own choice. No real statement is ever
committed to this repo; every test and demo statement is synthetic.

## Choices and their costs

Every decision record lists an option not taken and why. A few costs are worth saying
here in one place:

- No bank format is guessed ([ADR 0003](decisions/0003-importing-statements.md)). This
  makes every bank's CSV work from the first release, at the cost of one manual
  mapping step for every user, since [no preset is confirmed yet](reference.md#bank-csv-presets).
- Merchant names are grouped by an exact key after fixed cleaning steps, not by fuzzy
  matching ([ADR 0002](decisions/0002-detection-rules-and-thresholds.md)). This avoids
  merging two different merchants into one false recurring charge, at the cost of
  missing a series whose description changes in a way the cleaning steps do not cover.
- The web page fetches [Pyodide](glossary.md#pyodide) and the package's own wheel at
  build time, pinned by version and a SHA-256 hash, instead of committing the files or
  loading them from a public CDN ([ADR 0004](decisions/0004-web-door-pyodide-and-csp.md)).
  This keeps the repo small and the browser's set of trusted origins short, at the cost
  of needing the network to build the page.
