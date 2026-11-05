from __future__ import annotations

import pytest

from ai_shopping_agent.models import Requirements
from ai_shopping_agent.parser import RuleBasedRequirementParser


@pytest.mark.parametrize(
    ("case_text", "field", "expected"),
    [
        ("I need a laptop", "category", "laptop"),
        ("My maximum budget is $1,200", "max_price", 1200.0),
        ("Keep it under $950", "max_price", 950.0),
        ("It must have at least 32GB RAM", "min_ram_gb", 32),
        ("It needs 1TB SSD storage", "min_storage_gb", 1024),
        ("It needs 512GB SSD storage", "min_storage_gb", 512),
        ("Prefer battery life of 12 hours", "preferred_battery_hours", 12.0),
        ("Prefer 10+ hours of battery life", "preferred_battery_hours", 10.0),
        ("Weight should be under 1.6kg", "preferred_max_weight_kg", 1.6),
        ("This is for software development", "purpose", "software development"),
    ],
)
def test_extracts_requirement(case_text: str, field: str, expected: object) -> None:
    parsed = RuleBasedRequirementParser().parse(case_text)
    assert getattr(parsed, field) == expected


def test_follow_up_preserves_previous_values() -> None:
    parser = RuleBasedRequirementParser()
    previous = Requirements(category="laptop", max_price=1200, min_ram_gb=32, min_storage_gb=1024)
    updated = parser.parse("My maximum budget is $900 now", previous)
    assert updated.max_price == 900
    assert updated.min_ram_gb == 32
    assert updated.min_storage_gb == 1024


def test_ram_value_is_not_misclassified_as_storage() -> None:
    parsed = RuleBasedRequirementParser().parse("It must have at least 32GB RAM")
    assert parsed.min_ram_gb == 32
    assert parsed.min_storage_gb is None


def test_conflicting_budgets_request_clarification() -> None:
    parsed = RuleBasedRequirementParser().parse("My maximum budget is $900 but my max budget is $1,200")
    assert parsed.conflicts
    assert parsed.clarification_question


def test_conflicting_ram_request_clarification() -> None:
    parsed = RuleBasedRequirementParser().parse("I need at least 64GB RAM but at most 32GB RAM")
    assert parsed.conflicts
    assert "RAM" in (parsed.clarification_question or "")

