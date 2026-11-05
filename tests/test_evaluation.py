import json
from pathlib import Path

from ai_shopping_agent.evaluation.metrics import GATE_FILES, score_gates


def test_catalog_contains_at_least_30_products() -> None:
    catalog = json.loads(Path("data/catalog.json").read_text(encoding="utf-8"))
    assert len(catalog) >= 30
    assert len({product["product_id"] for product in catalog}) == len(catalog)


def test_scenario_manifest_contains_at_least_30_expected_outcomes() -> None:
    scenarios = json.loads(Path("tests/cases/scenarios.json").read_text(encoding="utf-8"))
    assert len(scenarios) >= 30
    assert all(case.get("expected") for case in scenarios)
    assert len({case["id"] for case in scenarios}) == len(scenarios)


def test_required_assessment_scenarios_are_covered() -> None:
    scenarios = json.loads(Path("tests/cases/scenarios.json").read_text(encoding="utf-8"))
    required = {f"REQ-{number:02}" for number in range(1, 11)}
    assert required <= {case["id"] for case in scenarios}


def test_quality_gates_cannot_pass_with_zero_discovered_tests() -> None:
    result = score_gates(test_failures=0, test_total=0)
    assert result["score"] == 0


def test_quality_gates_pass_with_clean_test_run_and_deliverables() -> None:
    result = score_gates(test_failures=0, test_total=1)
    assert result["score"] == 5


def test_targeted_gate_failure_reduces_quality_score() -> None:
    targeted = {
        name: {"exit_code": 0, "passed": 1, "failed": 0, "errors": 0}
        for name in GATE_FILES
    }
    targeted["dynamic_tools"] = {"exit_code": 1, "passed": 0, "failed": 1, "errors": 0}
    result = score_gates(test_failures=0, test_total=1, gate_test_results=targeted)
    assert result["score"] == 4

