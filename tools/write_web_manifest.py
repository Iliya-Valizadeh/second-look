"""Write `web/dist/manifest.json`, naming the wheel `make web-wheel` just built.

Usage: python tools/write_web_manifest.py --dist web/dist

The web page fetches this manifest at load time (a same-origin, no-query GET) so
`app.js` never has to hard-code the package version in the wheel's filename.

Only the Python standard library is used.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def find_wheel(dist_dir: Path) -> Path:
    wheels = sorted(dist_dir.glob("second_look-*.whl"))
    if not wheels:
        raise SystemExit(f"no second_look wheel found in {dist_dir}; run `make web-wheel` first")
    if len(wheels) > 1:
        raise SystemExit(f"more than one wheel in {dist_dir}: {[w.name for w in wheels]}")
    return wheels[0]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", default="web/dist", help="folder holding the built wheel")
    args = parser.parse_args(argv)

    dist_dir = Path(args.dist)
    wheel = find_wheel(dist_dir)
    manifest_path = dist_dir / "manifest.json"
    manifest_path.write_text(json.dumps({"wheel": wheel.name}, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {manifest_path} (wheel: {wheel.name})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
