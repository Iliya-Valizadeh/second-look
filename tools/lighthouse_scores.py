"""Copy the performance and accessibility scores from a Lighthouse JSON report into
`reports/metrics.json`, under a `lighthouse` key.

Usage: python tools/lighthouse_scores.py reports/lighthouse/report.json

This never runs Lighthouse itself and never invents a score. It only reads the
number Lighthouse already wrote (`categories.<name>.score`, 0 to 1) and rounds it to
a whole number out of 100, the form Lighthouse's own UI shows. Run Lighthouse first
(see `docs/reference.md`), then run this script, then commit both the report and the
updated `reports/metrics.json`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
METRICS_PATH = REPO_ROOT / "reports" / "metrics.json"

# The two categories the house standard's Lighthouse gate checks. Both must be 90 or
# more (docs/whats_weak.md and STATUS.md task "Bank presets and Lighthouse").
CATEGORIES = ("performance", "accessibility")


def read_scores(report: dict[str, Any]) -> dict[str, int]:
    scores: dict[str, int] = {}
    for name in CATEGORIES:
        try:
            raw = report["categories"][name]["score"]
        except KeyError as exc:
            raise ValueError(f"report has no categories.{name}.score") from exc
        if raw is None:
            raise ValueError(f"categories.{name}.score is null in this report")
        scores[name] = round(raw * 100)
    return scores


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", help="path to a Lighthouse JSON report")
    parser.add_argument(
        "--metrics", default=str(METRICS_PATH), help="metrics.json file to update in place"
    )
    args = parser.parse_args(argv)

    report_path = Path(args.report)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    scores = read_scores(report)

    try:
        report_display = report_path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        report_display = report_path.as_posix()

    metrics_path = Path(args.metrics)
    metrics: dict[str, Any] = json.loads(metrics_path.read_text(encoding="utf-8"))
    metrics["lighthouse"] = {
        "performance": scores["performance"],
        "accessibility": scores["accessibility"],
        "preset": "mobile",
        "report": report_display,
        "requested_url": report.get("requestedUrl"),
        "fetch_time": report.get("fetchTime"),
        "lighthouse_version": report.get("lighthouseVersion"),
    }
    metrics_path.write_text(
        json.dumps(metrics, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    print(f"performance={scores['performance']} accessibility={scores['accessibility']}")
    for name, score in scores.items():
        if score < 90:
            print(f"warning: {name} is below 90 ({score})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
