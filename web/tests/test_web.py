"""Headless-browser test for the web door (ADR 0004).

Loads `web/index.html` from a local static server, runs it against the committed
synthetic demo statement, and checks that the flags `make demo` also produces show
up on the page. It also records every network request the page makes and fails if
any of them:

- goes to another origin,
- uses a method other than GET,
- carries a query string, or
- asks for a path outside the fixed list of this site's own files.

This goes further than the CSP in `web/index.html`, which still allows requests to
the page's own origin. The CSP is meant to make a same-origin-only page possible;
this test is what actually checks that the page holds up its "nothing leaves your
browser" promise, independent of the CSP tag being present. Run it with `make
web-test`, which builds the Pyodide files and the wheel first.

Needs `web/pyodide/` and `web/dist/` to already exist (`make web-build`).
"""

from __future__ import annotations

import http.server
import mimetypes
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import Page, Request, sync_playwright

WEB_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = WEB_DIR.parent
DEMO_STATEMENT = REPO_ROOT / "tests" / "fixtures" / "synthetic_demo_statement.csv"

# Same fixture `make demo` runs, so the expected flags are the ones printed by
# `python -m second_look.demo` (checked by hand against that command's output).
EXPECTED_REASON_FRAGMENTS = (
    "NETFLIX.COM: $15.99 charged every month",
    "Two charges of $4.50 at COFFEE SHOP #4",
)

ALLOWED_EXACT_PATHS = {"/", "/index.html", "/style.css", "/app.js", "/bridge.py"}
ALLOWED_PREFIXES = ("/pyodide/", "/dist/")


class _Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def log_message(self, format, *args):  # noqa: A002 - matches base signature
        pass  # keep test output quiet; failures still show via assertions


mimetypes.add_type("application/wasm", ".wasm")
mimetypes.add_type("text/javascript", ".mjs")


@pytest.fixture(scope="session")
def server_url() -> Iterator[str]:
    if not (WEB_DIR / "pyodide" / "pyodide.mjs").exists():
        pytest.skip("web/pyodide/ is missing; run `make web-build` first")
    if not list((WEB_DIR / "dist").glob("second_look-*.whl")):
        pytest.skip("web/dist/ is missing the wheel; run `make web-build` first")

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)


def _path_is_allowed(path: str) -> bool:
    return path in ALLOWED_EXACT_PATHS or any(path.startswith(p) for p in ALLOWED_PREFIXES)


def _wait_until(check: Callable[[], bool], timeout_s: float = 60, interval_s: float = 0.25) -> None:
    """Poll `check` from outside the page instead of `wait_for_function` /
    `wait_for_selector`'s default strategy, both of which can ask the browser to
    evaluate a string as JavaScript in the page's own context. The page's CSP
    (ADR 0004) intentionally has no `'unsafe-eval'`, so that kind of wait fails on
    this page by design; reading attributes and text content does not need it.
    """
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(interval_s)
    raise TimeoutError(f"condition not met within {timeout_s}s")


def _is_visible(page: Page, selector: str) -> bool:
    return page.locator(selector).get_attribute("hidden") is None


def _run_the_demo_statement(page: Page, base_url: str) -> tuple[list[Request], str]:
    """Load the page, run it on the demo statement, and return every request the
    page made plus the rendered results section's text.
    """
    requests: list[Request] = []
    page.on("request", lambda request: requests.append(request))

    page.goto(base_url + "/", wait_until="load")
    _wait_until(lambda: "Ready" in (page.locator("#status").text_content() or ""))

    page.set_input_files("#file-input", str(DEMO_STATEMENT))
    _wait_until(lambda: _is_visible(page, "#screen-mapping"))

    # The demo statement's header words (Date, Description, Amount, Category) match
    # every mapping field's default suggestion, so no field needs changing here.
    page.click("#mapping-submit")
    _wait_until(lambda: _is_visible(page, "#screen-results"))

    results_text = page.locator("#results-list").inner_text()
    return requests, results_text


def test_the_page_shows_the_demo_statements_flags_and_makes_no_stray_request(
    server_url: str,
) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        try:
            requests, results_text = _run_the_demo_statement(page, server_url)
        finally:
            browser.close()

    for fragment in EXPECTED_REASON_FRAGMENTS:
        assert fragment in results_text, f"missing expected flag text: {fragment!r}"

    assert "fr" + "aud" not in results_text.lower()

    server_origin = urlsplit(server_url)
    violations = []
    for request in requests:
        parsed = urlsplit(request.url)
        if (parsed.scheme, parsed.netloc) != (server_origin.scheme, server_origin.netloc):
            violations.append(f"cross-origin request: {request.url}")
            continue
        if request.method != "GET":
            violations.append(f"non-GET request: {request.method} {request.url}")
        if parsed.query:
            violations.append(f"request with a query string: {request.url}")
        if not _path_is_allowed(parsed.path):
            violations.append(f"request outside the fixed file list: {request.url}")

    assert violations == [], "\n".join(violations)
    assert len(requests) > 5  # guards the test itself: it should have seen real traffic
