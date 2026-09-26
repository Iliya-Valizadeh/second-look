# One command for each step. CI runs the same targets.
# Every target runs inside the uv environment, so no global installs are needed.

PKG := second_look
RUN := uv run
DOCS := README.md CLAIMS.md CHANGELOG.md AI_USAGE.md $(wildcard MODEL_CARD.md DATASHEET.md) docs
WEB_PYODIDE_DIR := web/pyodide
WEB_DIST_DIR := web/dist

.PHONY: setup lint test eval demo check-docs web-pyodide web-wheel web-build web-test all

setup:
	uv sync

lint:
	$(RUN) ruff check .
	$(RUN) ruff format --check .
	$(RUN) mypy

test:
	$(RUN) pytest

eval:
	$(RUN) python -m evaluation.evaluate

demo:
	$(RUN) python -m $(PKG).demo

check-docs:
	$(RUN) python tools/ai_signs_check.py $(DOCS)
	$(RUN) python tools/claims_check.py $(DOCS)
	$(RUN) python tools/readability_check.py --glossary docs/glossary.md $(DOCS)
	$(RUN) python tools/links_check.py $(DOCS)
	$(RUN) python tools/readme_sections.py check README.md
	$(RUN) python tools/readme_sections.py repo-map README.md --check
	$(RUN) python tools/banned_words_check.py

# Door 2 (web) needs the network to fetch Pyodide and to build its wheel, so these
# targets are never part of `demo` or `all`. ADR 0004 pins the Pyodide version and
# the archive's hash; a wrong hash stops web-pyodide with an error.
web-pyodide:
	$(RUN) python tools/fetch_pyodide.py --out $(WEB_PYODIDE_DIR)

web-wheel:
	uv build --wheel --out-dir $(WEB_DIST_DIR)
	$(RUN) python tools/write_web_manifest.py --dist $(WEB_DIST_DIR)

web-build: web-pyodide web-wheel

# The Playwright test loads the built page in a headless browser (ADR 0004). It
# needs web-build first and a browser binary, which `playwright install` downloads.
web-test: web-build
	$(RUN) playwright install --with-deps chromium
	$(RUN) pytest web/tests -p no:cacheprovider --no-cov -q

all: setup lint test eval demo check-docs
