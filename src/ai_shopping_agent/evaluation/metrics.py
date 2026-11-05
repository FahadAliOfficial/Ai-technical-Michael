from __future__ import annotations

import json
from pathlib import Path
from typing import Any


GATE_FILES = {
    "requirements_and_state": [
        "src/ai_shopping_agent/parser.py",
        "src/ai_shopping_agent/state.py",
        "tests/test_parser.py",
        "tests/test_state_updates.py",
    ],
    "dynamic_tools": [
        "src/ai_shopping_agent/tools/registry.py",
        "src/ai_shopping_agent/tools/adapter.py",
        "data/tool_manifest.json",
        "tests/test_dynamic_tools.py",
    ],
    "validation_and_ranking": [
        "src/ai_shopping_agent/validation.py",
        "src/ai_shopping_agent/ranking.py",
        "tests/test_validation.py",
        "tests/test_ranking.py",
    ],
    "resilience_and_auditability": [
        "src/ai_shopping_agent/audit.py",
        "tests/test_error_recovery.py",
        "evidence/sample-run.jsonl",
    ],
    "tests_and_documentation": [
        "README.md",
        "docs/architecture.md",
        "docs/decisions.md",
        "docs/limitations.md",
        "docs/live-defense-runbook.md",
        "tests/cases/scenarios.json",
    ],
}

GATE_TESTS = {
    "requirements_and_state": [
        "tests/test_parser.py",
        "tests/test_state_updates.py",
        "tests/test_agent_workflow.py",
    ],
    "dynamic_tools": [
        "tests/test_tool_registry.py",
        "tests/test_dynamic_tools.py",
        "tests/test_model_client.py",
    ],
    "validation_and_ranking": [
        "tests/test_validation.py",
        "tests/test_ranking.py",
        "tests/test_agent_workflow.py",
    ],
    "resilience_and_auditability": [
        "tests/test_error_recovery.py",
        "tests/test_agent_workflow.py",
    ],
    "tests_and_documentation": [
        "tests/test_evaluation.py",
    ],
}


def score_gates(
    test_failures: int,
    test_total: int,
    root: Path = Path("."),
    gate_test_results: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    scenario_count = 0
    catalog_count = 0
    try:
        scenario_count = len(json.loads((root / "tests/cases/scenarios.json").read_text(encoding="utf-8")))
        catalog_count = len(json.loads((root / "data/catalog.json").read_text(encoding="utf-8")))
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    gates: dict[str, Any] = {}
    for name, files in GATE_FILES.items():
        missing = [path for path in files if not (root / path).is_file()]
        targeted = (gate_test_results or {}).get(name)
        targeted_passed = (
            targeted is None
            or (
                targeted.get("exit_code") == 0
                and targeted.get("passed", 0) > 0
                and targeted.get("failed", 0) == 0
                and targeted.get("errors", 0) == 0
            )
        )
        passed = test_total > 0 and test_failures == 0 and not missing and targeted_passed
        if name == "tests_and_documentation":
            passed = passed and scenario_count >= 30 and catalog_count >= 30
        gates[name] = {
            "passed": passed,
            "missing_files": missing,
            "targeted_tests": targeted,
        }
    return {
        "score": sum(1 for gate in gates.values() if gate["passed"]),
        "maximum_score": 5,
        "gates": gates,
        "scenario_count": scenario_count,
        "catalog_count": catalog_count,
    }

