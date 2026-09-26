# How to map a bank's CSV columns

second-look never guesses a bank's export format
([ADR 0003](../decisions/0003-importing-statements.md)). No preset is confirmed for any
bank yet (see [the reference page](../reference.md#bank-csv-presets)), so every user
maps their own file's columns by hand. This guide shows how, for any bank.

## Before you start

Export your statement as CSV from your bank's own website or app. Open the file in a
plain text editor, or a spreadsheet program set to show text, not a spreadsheet app that
might reformat dates or drop leading zeros. Look at the header row and the first two or
three data rows.

## 1. Find the header row

Most exports have one header row naming each column, such as `Date,Description,Amount`.
If your file has no header row, count the columns instead; second-look's `--no-header`
flag then names them by position, starting at `0`.

## 2. Find the date column and its format

Look at the date values. The three formats second-look understands are `YYYY-MM-DD`,
`MM/DD/YYYY` and `DD/MM/YYYY`. You choose one; the tool does not suggest a format, and
`YYYY-MM-DD` is the default. If the day is above `12` in any row, you can tell whether
the file is day-first or month-first. If every day is `12` or lower, both read every
row, and a wrong choice gives wrong dates with no message. Check the bank's help page
or a date you remember.

## 3. Find the description column

This is usually called `Description`, `Memo` or `Details`. Some exports split it into
two columns, such as a merchant name and a reference number. second-look can join more
than one description column with a space; give `--description-column` more than once,
or check more than one box on the web page's mapping screen.

## 4. Find the amount column, or the debit and credit columns

Some exports have one amount column, where the sign says whether money left or entered
the account. Others split debits and credits into two columns. Check a row you know was
a purchase:

- One signed column: does a purchase show as a negative number (`-12.34`) or a positive
  one (`12.34`)? That decides `--sign-convention charges-negative` or
  `charges-positive`.
- Two columns: a purchase should have a value in the debit column, and the credit
  column should be blank for that row.

## 5. Check the optional category column

If your export has a column that names a spending category, such as `Groceries` or
`Dining`, second-look can use it for the per-category unusual-charge test
([ADR 0002](../decisions/0002-detection-rules-and-thresholds.md)). Give it with
`--category-column`. Without one, that test does not run; only the per-merchant test
does.

## 6. Run it and check the summary

```bash
uv run second-look your-statement.csv \
  --date-column Date --date-format YYYY-MM-DD \
  --description-column Description \
  --amount-column Amount --sign-convention charges-negative
```

Read the summary line first: rows read (the header row counts), rows used, and any
skipped rows with a reason. A wrong sign convention does not crash the tool, and the
summary does not show it. It silently turns every charge into money coming in, and the
tool then finds nothing. So if a statement you expected flags for shows none, check the
sign first. Check that the yearly costs and reasons on the flags make sense before
trusting them. On the web page, the preview table shows your file's first rows as they
are in the file, not as the tool reads them. Use it to find a purchase and check its
sign before you press "Show results".

## If you have a bank's own header row

A confirmed preset needs a link to the bank's own help page showing the exact header
row, or a real header row (the header line only, with no transaction rows) from Iliya
([ADR 0003](../decisions/0003-importing-statements.md)). If you have one, open an issue
with the source.
