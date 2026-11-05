from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

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
    coverage_match = re.search(r"TOTAL\s+.*?(\d+)%", combined)
    executed = counts["passed"] + counts["failed"] + counts["errors"]
    return {
        **counts,
        "total": executed,
        "success_rate_percent": round(100 * counts["passed"] / executed, 2) if executed else 0,
        "exit_code": completed.returncode,
        "coverage_percent": int(coverage_match.group(1)) if coverage_match else None,
        "output": combined if completed.returncode else None,
    }


def _run_pytest(
    paths: list[str] | None = None,
    *,
    live: bool = False,
    coverage: bool = False,
) -> dict[str, object]:
    command = [sys.executable, "-m", "pytest", "-o", "addopts=", "-q"]
    if not live:
        command.extend(["-m", "not live"])
    if paths:
        command.extend(paths)
    if coverage:
        command.extend(
            [
                "--cov=ai_shopping_agent",
                "--cov-branch",
                "--cov-report=term",
                "--cov-fail-under=85",
            ]
        )
    environment = os.environ.copy()
    if live:
        environment["RUN_LIVE_OPENAI_TESTS"] = "1"
    started = perf_counter()
    completed = subprocess.run(command, check=False, capture_output=True, text=True, env=environment)
    result = _parse_test_result(completed)
    result["command"] = " ".join(command)
    result["duration_seconds"] = round(perf_counter() - started, 3)
    return result


def run(
    output: Path = Path("evidence/evaluation-results.json"),
    *,
    include_live: bool = False,
) -> dict[str, object]:
    tests = _run_pytest(coverage=True)
    gate_tests = {name: _run_pytest(paths) for name, paths in GATE_TESTS.items()}
    gates = score_gates(
        int(tests["failed"]) + int(tests["errors"]),
        int(tests["total"]),
        gate_test_results=gate_tests,
        coverage_percent=tests.get("coverage_percent"),
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
        "failure_analysis": [
            output
            for output in (
                tests.get("output") if tests["exit_code"] != 0 else None,
                live_tests.get("output") if include_live and live_tests.get("exit_code") != 0 else None,
            )
            if output
        ],
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
