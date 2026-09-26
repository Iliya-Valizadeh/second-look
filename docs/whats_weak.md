# What's weak

The full list of limits. The README shows the top few. Rank them by how much each one
could change the main result, with the largest first. Say what was done about each
one, even if the answer is "nothing yet".

| Rank | Weakness | How much it could change the result | What was done |
|---|---|---|---|
| 1 | No confirmed bank presets (RBC, TD, CIBC, BMO, Scotiabank) | Every user still does the column-mapping step by hand, even for a common bank. [ADR 0003](decisions/0003-importing-statements.md) requires a preset to come from the bank's own help page or a real header row from Iliya; a 2026-09-26 search of each bank's own help and support pages found none that lists the literal CSV column header names, so zero presets exist. A preset would only save a setup step; it changes no detection rule or result. | Wanted, not done. Checked each bank's own site (not third-party pages); see the "Bank CSV presets" row in `docs/reference.md` for what was and was not found. Any of the five would help: RBC, TD, CIBC, BMO, Scotiabank. |
