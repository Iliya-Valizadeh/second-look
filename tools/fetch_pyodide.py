"""Fetch the pinned Pyodide core files for the web door (ADR 0004).

Usage: python tools/fetch_pyodide.py [--out web/pyodide]

Downloads the Pyodide core archive from its GitHub release, checks its SHA-256
against the value pinned in ADR 0004, and extracts the five files the web door
needs into the output folder. A wrong hash stops the build with an error and
writes nothing. This script is the one place in the repo that is allowed to reach
the network for the web door; `make demo` and the tests never call it.

Only the Python standard library is used.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import sys
import tarfile
import urllib.request
from pathlib import Path

# Pinned in docs/decisions/0004-web-door-pyodide-and-csp.md. Changing the version
# means changing this hash too, then rerunning the Playwright test in web/tests/.
PYODIDE_VERSION = "314.0.7"
CORE_SHA256 = "2abdcc2e35208af406e07724cffa85bc582ced97e9028383ecf5462541393f95"
CORE_URL = (
    f"https://github.com/pyodide/pyodide/releases/download/"
    f"{PYODIDE_VERSION}/pyodide-core-{PYODIDE_VERSION}.tar.bz2"
)

# The five files the web door loads from the core archive (ADR 0004).
NEEDED_FILES = (
    "pyodide.mjs",
    "pyodide.asm.mjs",
    "pyodide.asm.wasm",
    "python_stdlib.zip",
    "pyodide-lock.json",
)


def _download(url: str) -> bytes:
    with urllib.request.urlopen(url) as response:  # noqa: S310 - pinned GitHub release URL
        return response.read()


def fetch_core_archive() -> bytes:
    data = _download(CORE_URL)
    digest = hashlib.sha256(data).hexdigest()
    if digest != CORE_SHA256:
        raise SystemExit(
            f"pyodide-core-{PYODIDE_VERSION}.tar.bz2 hash mismatch: "
            f"got {digest}, expected {CORE_SHA256}. Not extracting anything."
        )
    return data


def extract_needed_files(archive_bytes: bytes, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    remaining = set(NEEDED_FILES)
    with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:bz2") as tar:
        for member in tar:
            name = Path(member.name).name
            if name in remaining and member.isfile():
                extracted = tar.extractfile(member)
                if extracted is None:
                    continue
                (out_dir / name).write_bytes(extracted.read())
                remaining.discard(name)
    if remaining:
        raise SystemExit(f"pyodide-core-{PYODIDE_VERSION}.tar.bz2 is missing: {sorted(remaining)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        default="web/pyodide",
        help="folder to extract the five core files into (default: web/pyodide)",
    )
    args = parser.parse_args(argv)

    out_dir = Path(args.out)
    print(f"Fetching pyodide-core-{PYODIDE_VERSION}.tar.bz2 ...")
    archive_bytes = fetch_core_archive()
    print(f"Hash checked: {CORE_SHA256}")
    extract_needed_files(archive_bytes, out_dir)
    for name in NEEDED_FILES:
        print(f"  wrote {out_dir / name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
