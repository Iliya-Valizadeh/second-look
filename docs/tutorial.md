# Tutorial

This page walks you through one full run of second-look, from a fresh clone to
the demo output. You need `uv`, `make`, and the Python version named in
`pyproject.toml`. `uv` can install that Python for you.

## Step 1: get the code

```bash
git clone https://github.com/Iliya-Valizadeh/second-look.git
cd second-look
```

## Step 2: install

```bash
make setup
```

## Step 3: run the demo

```bash
make demo
```

The demo runs the command line on a small, made-up statement
(`tests/fixtures/synthetic_demo_statement.csv`). It prints a note that the statement
is made up, then the list of charges worth a second look, then a line saying how many
rows it read, and the tool's not-financial-advice footer. No file is downloaded and no
key is needed.

## Step 4: run it on your own statement

```bash
uv run second-look your-statement.csv \
  --date-column Date --description-column Description \
  --amount-column Amount --sign-convention charges-negative
```

Change the column names to match your file's header row, and add `--category-column`
if your export has one. See [the reference page](reference.md#command-line-flags) for
every flag, including separate debit and credit columns. Add `--json` to get the same
result as JSON instead of plain text.
