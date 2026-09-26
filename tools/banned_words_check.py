"""Repo-wide search for the one word ADR 0005 says the tool never uses.

Usage: python tools/banned_words_check.py [PATH ...]

ADR 0005 bans a handful of words from the tool's own output (reason strings, its
titles and footer); `tests/test_wording.py` checks those against the running code.
This script checks something wider and simpler: that the one word ADR 0005 spells
out letter by letter (built from parts below, so it appears nowhere in this repo
as a plain word) never appears anywhere in the repo's source or docs, spelled out
normally, by mistake.

With no PATH given, it searches `src/`, `web/`, `tests/` and `docs/`, plus every
Markdown file at the repo root. Binary files, `.git/`, `__pycache__/`,
`node_modules/`, and any downloaded or vendored Pyodide folder (`**/pyodide/`) are
skipped. The check is case-insensitive.

Exit code 0 means zero hits. Exit code 1 means at least one hit.
Only the Python standard library is used.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Built from parts, as ADR 0005 asks, so the plain word appears nowhere in this repo.
BANNED_WORD = "fr" + "aud"

SKIP_DIR_NAMES = {".git", "__pycache__", "node_modules", "pyodide", ".mypy_cache", ".ruff_cache"}

TEXT_SUFFIXES = {".py", ".js", ".mjs", ".html", ".css", ".md", ".json", ".toml", ".yml", ".yaml"}

DEFAULT_ROOTS = ("src", "web", "tests", "docs")


def _iter_files(roots: list[Path]) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        if root.is_file():
            files.append(root)
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if any(part in SKIP_DIR_NAMES for part in path.relative_to(REPO_ROOT).parts):
                continue
            if path.suffix.lower() in TEXT_SUFFIXES:
                files.append(path)
    return files


def find_hits(files: list[Path]) -> list[str]:
    hits: list[str] = []
    for path in files:
        rel = path.relative_to(REPO_ROOT) if path.is_absolute() else path
        try:
            text = path.read_text(encoding="utf-8").lower()
        except (UnicodeDecodeError, OSError):
            continue
        if BANNED_WORD in text:
            hits.append(f"{rel}: contains the banned word")
    return hits


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv:
        roots = [Path(p) for p in argv]
    else:
        roots = [REPO_ROOT / name for name in DEFAULT_ROOTS if (REPO_ROOT / name).is_dir()]
        roots += sorted(REPO_ROOT.glob("*.md"))

    hits = find_hits(_iter_files(roots))
    if hits:
        print("Banned word found:")
        for hit in hits:
            print(f"  {hit}")
        return 1
    print("No banned word found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
