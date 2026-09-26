# 0005: Privacy and wording

Date: 2026-09-25. Status: accepted.

## Context

People will open this tool with their own bank statements. Two things can hurt them.
The first is their data going somewhere they did not expect. The second is words that
scare them or tell them what to do with their money. A flag only means a charge matches
a pattern. It does not mean anyone did anything wrong, and the tool cannot know.

This record uses the spelled-out form `f-r-a-u-d` for the one word the tool never
says. Writing it this way keeps a plain search of this repo for that word at zero
hits, which is the check described below.

## Options

For the words on screen:

1. Neutral words only. Flags are "worth a second look", reasons state facts, and no
   words suggest a crime.
2. Security words, such as "suspicious" or "possible f-r-a-u-d". They grab attention,
   but they claim more than a pattern can show and can frighten people for no reason.

For learning whether flags are right:

1. A local-only feedback file. The user marks flags and saves a file on their own
   computer. Nothing is sent.
2. A feedback form that sends answers to a server. It gathers more answers, but it
   needs a server, an upload path and a privacy policy, and it breaks the promise that
   nothing leaves the browser.
3. No feedback at all. It is simpler, but then the tool has no way to learn about real
   statements, since synthetic tests cannot show real-world accuracy.

## Decision

Option 1 in both lists.

### Words the tool never uses

- The word `f-r-a-u-d`, in any form, never appears in the tool's output, its web page,
  its code, its code comments, its docs, its test names or its commit messages from
  now on.
- The tool also avoids other words that suggest a crime or a threat: "suspicious",
  "scam", "stolen", "criminal", "alert" and "warning".
- The tool uses "worth a second look" as the section title and the name for flags.
- The one place the banned word may exist is inside the test that checks for it. That
  test builds the word from parts (for example `"fr" + "aud"`), so the plain word still
  appears nowhere in the repo.
- This repo does not name or link the portfolio's flagship project, because that
  project's name contains the banned word. The portfolio site and profile can connect
  the two.

How it is checked:

- A test runs the engine on synthetic statements and fails if any reason string, title
  or label contains a banned word, ignoring case. It is part of the "Engine part 2" task.
- A repo-wide search for the banned word runs in CI over `src/`, `web/`, `tests/`,
  `docs/` and every Markdown file. It is added with the web page task.
- Commit messages are checked by hand at the review pass before each merge.

### Not financial advice

The page footer, the end of the command line output and the README all say this, in
these words:

> This tool points out charges you may want to look at again. It is not financial
> advice. It cannot tell whether a charge is right or wrong. Only you, the merchant or
> your bank can.

Reason strings describe what the tool saw. They never tell the user what to do with
their money. For example, they never say "cancel this" or "you should". The page may
say that the merchant or the bank can explain a charge.

### Local-only feedback export

- On the web page, each flag has three choices: "Right", "Wrong" and "Not sure".
- A "Save my feedback" button builds a JSON file in the browser and hands it to the
  browser's normal download. No request is made. The CSP in
  [ADR 0004](0004-web-door-pyodide-and-csp.md) would block one to any other origin.
- The file holds, for each marked flag: the flag type, the rule that fired, its numbers
  (such as the ratio or the score), the period for recurring charges, and the user's
  choice. It also holds the tool version.
- By default the file does not hold merchant names, descriptions, dates or amounts. A
  user who shares the file (for example in a GitHub issue) then shares no personal
  details. A checkbox can add merchant names, and it is off by default.
- Sharing the file is always the user's own choice. The page says so next to the
  button.
- The feedback choices are kept only in the page's memory. They are gone when the tab
  closes, unless the user saves the file.

### Data in the repo

- No real statement, and no row from one, is ever committed. Tests, the demo and the
  evaluation use synthetic statements only. Each synthetic file says it is synthetic in
  its name and in a comment line or note next to it.
- The only real bank data allowed is a header row from a bank's export, under the
  rules in [ADR 0003](0003-importing-statements.md). It holds column names only.
- `.gitignore` already blocks `*.csv` outside `tests/fixtures/`, so a statement dropped
  into the repo folder by mistake is not committed.

## Consequences

- The tool can be wrong without harm from its wording: a wrong flag reads as "look
  again", not as an accusation.
- Tests and CI check the wording rules, so they do not depend on memory.
- Feedback will be rare, since it depends on users choosing to share a file. The
  evaluation cannot count on it, and `docs/whats_weak.md` should say so.
- The feedback file leaves out merchant names by default, so it is less useful for
  finding naming problems. That is the price of making it safe to share.

## Option not taken

A feedback form that sends answers to a server was not chosen, because it would break
the promise that nothing leaves the browser.
