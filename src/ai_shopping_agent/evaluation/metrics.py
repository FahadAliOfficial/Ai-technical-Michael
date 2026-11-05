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


def score_gates(test_failures: int, test_total: int, root: Path = Path(".")) -> dict[str, Any]:
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
        passed = test_total > 0 and test_failures == 0 and not missing
        if name == "tests_and_documentation":
            passed = passed and scenario_count >= 30 and catalog_count >= 30
        gates[name] = {"passed": passed, "missing_files": missing}
    return {
        "score": sum(1 for gate in gates.values() if gate["passed"]),
        "maximum_score": 5,
        "gates": gates,
        "scenario_count": scenario_count,
        "catalog_count": catalog_count,
    }

