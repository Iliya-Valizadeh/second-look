# 0001: One engine, two doors

Date: 2026-09-25. Status: accepted.

## Context

`second-look` reads a bank or card statement and lists charges worth a second look.
People reach it in two ways. Technical users install it with `pip` and run a command
(door 1). Everyone else opens a web page where the same Python code runs inside the
browser through Pyodide, a build of Python for WebAssembly (door 2). Both doors must
give the same answer for the same file, so the logic can exist only once.

Pyodide ships the Python standard library in its core download. Any other package
(for example numpy or pandas) is a separate wheel that the page must fetch and load.
The Pyodide release chosen in [ADR 0004](0004-web-door-pyodide-and-csp.md) is
`314.0.7`, which runs CPython `3.14.2`. This was checked in two ways: the release's
`pyodide-lock.json` says `"python": "3.14.2"`, and `sys.version` printed `3.14.2` when
the core files ran in headless Chrome.

In that same run, these standard library modules imported with no error: `csv`,
`datetime`, `decimal`, `statistics`, `re`, `unicodedata`, `dataclasses`, `enum`,
`math`, `json`, `io`, `typing`, `collections`, `itertools` and `functools`. They cover
everything the engine needs. The data is small. A statement has hundreds or a few
thousand rows, so there is no speed reason to reach for numpy.

The template's `pyproject.toml` sets `requires-python = ">=3.11"`, and Iliya's machine
runs Python `3.11`.

## Options

1. A core that uses only the standard library. The web page loads nothing beyond the
   Pyodide core files. The cost is writing the median absolute deviation and the
   grouping helpers by hand, which is a few lines each. `statistics.median` and the
   `csv` module already exist.
2. A core that uses pandas. Grouping and date handling get shorter. The cost is that the
   page must also fetch the pandas and numpy wheels, and every user waits for them.
3. Two separate code bases: Python for the command line and JavaScript for the page.
   The page gets lighter. The cost is two copies of every rule, and they will drift.

## Decision

Option 1. The core package `src/second_look/` uses only the Python standard library,
so the page needs the Pyodide core files and this package's own wheel, nothing else.
The core has no runtime dependencies in `pyproject.toml`. Money amounts use
`decimal.Decimal`, so cents are exact and yearly totals do not pick up float error.
Scores that are not money (such as z-scores) use `float`.

Python versions:

- The lowest version the core must run on is `3.11`. It matches the template and the
  machine it is built on, and it lets `pip` users on older systems install it. The core
  must not use syntax newer than `3.11` (for example the `type X = ...` statement from
  `3.12`).
- The highest version that matters is the one inside Pyodide, `3.14.2`. The core must
  also pass its tests there.
- The CI matrix will run the tests on `3.11` and `3.14`. That is a later CI change, not
  part of this decision record.

Where input and output live:

- The core does no input or output. It does not open files, print, read the clock, read
  environment variables, use random numbers or touch the network. It takes the statement
  as a `str` (or `bytes` it decodes itself), a column mapping and any settings. It
  returns plain data classes that turn into JSON.
- The date the analysis treats as "today" is the last date in the statement. It is never
  read from the clock, so the same file always gives the same flags.
- Door 1 is `src/second_look/cli.py`. It is the only module in the package that reads
  files, writes files or prints. It reads the CSV bytes, calls the core and prints text
  or JSON.
- Door 2 lives under `web/`. JavaScript reads the file the user picks with the browser's
  File API, passes the text to Python, and draws the result. Python in the browser never
  sees a file path.
- A test will check the rule. It will parse every core module and fail if one imports
  `os`, `pathlib`, `sys`, `socket`, `urllib`, `http`, `subprocess` or `random`, or calls
  `open` or `print`. `cli.py` is the one allowed exception.

## Consequences

- Both doors run the same functions, so one set of tests covers the logic for both.
- The page downloads only Pyodide's core and one small wheel. This helps the Lighthouse
  performance target and keeps the privacy story short.
- Hand-written statistics need their own unit tests, including edge cases such as an
  even count and a spread of zero.
- A later change that wants a third-party package must replace this decision with a new
  one and show that Pyodide can load that package from the same origin.

## Option not taken

pandas in the core was not chosen, because the page would fetch extra wheels for work
the standard library already does on data this small.
