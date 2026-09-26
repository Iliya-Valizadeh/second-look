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

## Step 5: try the web page

The web page (Door 2) runs the same rules inside your browser with
[Pyodide](glossary.md#pyodide), so a statement never has to leave your device. There is
no live page yet; enabling GitHub Pages is a "Needs Iliya" item. To try it on your own
machine, build it once:

```bash
make web-build
```

Unlike `make demo`, this needs the network once, to fetch Pyodide and build the
package's own wheel ([ADR 0004](decisions/0004-web-door-pyodide-and-csp.md)). Then serve
the `web/` folder and open it in a browser:

```bash
python -m http.server 8000 --directory web
```

Open `http://127.0.0.1:8000/` and use the same demo statement as step 3:

1. Drop `tests/fixtures/synthetic_demo_statement.csv` on the page, or choose it with the
   file picker.
2. On the mapping screen, check the preview rows, then set the date column to
   `Date` in format `YYYY-MM-DD`, the description column to `Description`, the amount
   column to `Amount` with "Charges are negative", and the category column to
   `Category`.
3. Press "Show results" to see the same flags `make demo` prints, now as cards you can
   mark right, wrong or not sure and save to a local feedback file.
