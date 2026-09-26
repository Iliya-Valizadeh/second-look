"""Tests for `tools/lighthouse_scores.py`, on a small hand-built Lighthouse report.

No Lighthouse run happens here; this only checks that the script reads the score
fields Lighthouse's JSON format defines and writes them into a metrics file
unchanged otherwise. Runs the script as a subprocess, the way `make` does, so this
test does not need `tools/` on `mypy`'s or `ruff`'s path (both check only `src`,
`tests` and `evaluation`; `tools/` is copied from `ds-project-standard` and checked
there).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "tools" / "lighthouse_scores.py"


def _report(performance: float, accessibility: float) -> dict[str, Any]:
    return {
        "lighthouseVersion": "12.0.0",
        "requestedUrl": "http://127.0.0.1:8000/",
        "fetchTime": "2026-09-26T00:00:00.000Z",
        "categories": {
            "performance": {"score": performance},
            "accessibility": {"score": accessibility},
        },
    }


def _run(report_path: Path, metrics_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(report_path), "--metrics", str(metrics_path)],
        capture_output=True,
        text=True,
    )


def test_scores_round_to_a_whole_number_and_other_metrics_keys_stay(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(_report(0.97, 1.0)), encoding="utf-8")

    metrics_path = tmp_path / "metrics.json"
    metrics_path.write_text(json.dumps({"headline": {"value": 0.5}}), encoding="utf-8")

    result = _run(report_path, metrics_path)
    assert result.returncode == 0, result.stderr

    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert metrics["headline"] == {"value": 0.5}
    assert metrics["lighthouse"]["performance"] == 97
    assert metrics["lighthouse"]["accessibility"] == 100
    assert metrics["lighthouse"]["preset"] == "mobile"


def test_a_score_below_90_prints_a_warning_but_still_writes_it(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(_report(0.62, 0.99)), encoding="utf-8")

    metrics_path = tmp_path / "metrics.json"
    metrics_path.write_text(json.dumps({}), encoding="utf-8")

    result = _run(report_path, metrics_path)
    assert result.returncode == 0, result.stderr
    assert "performance is below 90" in result.stderr

    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert metrics["lighthouse"]["performance"] == 62


def test_a_report_missing_a_category_fails_clearly(tmp_path: Path) -> None:
    report = _report(0.97, 1.0)
    del report["categories"]["accessibility"]
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")

    metrics_path = tmp_path / "metrics.json"
    metrics_path.write_text(json.dumps({}), encoding="utf-8")

    result = _run(report_path, metrics_path)
    assert result.returncode != 0
    assert "accessibility" in result.stderr
