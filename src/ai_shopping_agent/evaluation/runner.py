from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import os
from datetime import datetime, timezone
from pathlib import Path

from .metrics import GATE_TESTS, score_gates


def _parse_test_result(completed: subprocess.CompletedProcess[str]) -> dict[str, object]:
    combined = f"{completed.stdout}\n{completed.stderr}".strip()
    patterns = {
        "passed": r"(\d+) passed",
        "failed": r"(\d+) failed",
        "errors": r"(\d+) error",
        "skipped": r"(\d+) skipped",
        "deselected": r"(\d+) deselected",
    }
    counts = {
        name: int(match.group(1)) if (match := re.search(pattern, combined)) else 0
        for name, pattern in patterns.items()
    }
    executed = counts["passed"] + counts["failed"] + counts["errors"]
    return {
        **counts,
        "total": executed,
        "success_rate_percent": round(100 * counts["passed"] / executed, 2) if executed else 0,
        "exit_code": completed.returncode,
        "output": combined if completed.returncode else None,
    }


def _run_pytest(paths: list[str] | None = None, *, live: bool = False) -> dict[str, object]:
    command = [sys.executable, "-m", "pytest", "-o", "addopts=", "-q"]
    if not live:
        command.extend(["-m", "not live"])
    if paths:
        command.extend(paths)
    environment = os.environ.copy()
    if live:
        environment["RUN_LIVE_OPENAI_TESTS"] = "1"
    completed = subprocess.run(command, check=False, capture_output=True, text=True, env=environment)
    result = _parse_test_result(completed)
    result["command"] = " ".join(command)
    return result


def run(
    output: Path = Path("evidence/evaluation-results.json"),
    *,
    include_live: bool = False,
) -> dict[str, object]:
    tests = _run_pytest()
    gate_tests = {name: _run_pytest(paths) for name, paths in GATE_TESTS.items()}
    gates = score_gates(
        int(tests["failed"]) + int(tests["errors"]),
        int(tests["total"]),
        gate_test_results=gate_tests,
    )
    live_tests = _run_pytest(["tests/test_live_openai.py"], live=True) if include_live else {
        "executed": False,
        "reason": "Run with --live to execute paid OpenAI integration tests.",
    }
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tests": tests,
        "live_openai_tests": live_tests,
        "quality": gates,
        "failure_analysis": [] if tests["exit_code"] == 0 else [tests["output"]],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run tests and score the five assessment quality gates")
    parser.add_argument("--output", type=Path, default=Path("evidence/evaluation-results.json"))
    parser.add_argument("--live", action="store_true", help="Also run paid OpenAI integration tests")
    args = parser.parse_args()
    report = run(args.output, include_live=args.live)
    live_failed = args.live and report["live_openai_tests"].get("exit_code") != 0
    if report["tests"]["exit_code"] != 0 or report["quality"]["score"] != 5 or live_failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
