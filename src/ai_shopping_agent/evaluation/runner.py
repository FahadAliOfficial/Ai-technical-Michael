from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from .metrics import score_gates


def run(output: Path = Path("evidence/evaluation-results.json")) -> dict[str, object]:
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-o", "addopts=", "-q"],
        check=False,
        capture_output=True,
        text=True,
    )
    combined = f"{completed.stdout}\n{completed.stderr}".strip()
    passed_match = re.search(r"(\d+) passed", combined)
    failed_match = re.search(r"(\d+) failed", combined)
    error_match = re.search(r"(\d+) error", combined)
    passed = int(passed_match.group(1)) if passed_match else 0
    failed = int(failed_match.group(1)) if failed_match else 0
    errors = int(error_match.group(1)) if error_match else 0
    total = passed + failed + errors
    gates = score_gates(failed + errors, total)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "command": f"{sys.executable} -m pytest -o addopts= -q",
        "tests": {
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "total": total,
            "success_rate_percent": round(100 * passed / total, 2) if total else 0,
            "exit_code": completed.returncode,
        },
        "quality": gates,
        "failure_analysis": [] if completed.returncode == 0 else [combined],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run tests and score the five assessment quality gates")
    parser.add_argument("--output", type=Path, default=Path("evidence/evaluation-results.json"))
    args = parser.parse_args()
    report = run(args.output)
    if report["tests"]["exit_code"] != 0 or report["quality"]["score"] != 5:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
