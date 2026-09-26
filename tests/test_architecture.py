"""The core has no I/O (ADR 0001).

This parses every module in `second_look` and fails if one imports a module that
does file, network, clock or randomness I/O, or calls `open` or `print`. `cli.py` is
allowed, because it is Door 1 and its whole job is to read files and print. `demo.py`
is also allowed: it is not the engine, only a thin driver, like `cli.py`, that runs
Door 1 on the committed demo statement for `make demo`.
"""

from __future__ import annotations

import ast
from pathlib import Path

import second_look

BANNED_IMPORTS = frozenset(
    {"os", "pathlib", "sys", "socket", "urllib", "http", "subprocess", "random"}
)
BANNED_CALLS = frozenset({"open", "print"})
ALLOWED_EXCEPTIONS = frozenset({"cli", "demo"})

PACKAGE_DIR = Path(second_look.__file__).resolve().parent


def _module_files() -> list[Path]:
    return [
        path
        for path in PACKAGE_DIR.glob("*.py")
        if path.stem not in ALLOWED_EXCEPTIONS and path.name != "__init__.py"
    ]


def _check_module(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    problems: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top_level = alias.name.split(".")[0]
                if top_level in BANNED_IMPORTS:
                    problems.append(f"{path.name}:{node.lineno}: imports {alias.name!r}")
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] in BANNED_IMPORTS:
                problems.append(f"{path.name}:{node.lineno}: imports {node.module!r}")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in BANNED_CALLS:
                problems.append(f"{path.name}:{node.lineno}: calls {node.func.id}()")
    return problems


def test_no_module_does_file_network_clock_or_random_io() -> None:
    problems = [p for path in _module_files() for p in _check_module(path)]
    assert problems == []


def test_there_is_at_least_one_module_to_check() -> None:
    # Guards against the glob above silently matching nothing.
    assert len(_module_files()) >= 4
