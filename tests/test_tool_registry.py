from __future__ import annotations

import pytest

from ai_shopping_agent.tools.adapter import ArgumentAdapter, SchemaValidationError, validate_arguments


def test_argument_adapter_uses_parameter_descriptions_not_fixed_names() -> None:
    schema = {
        "type": "object",
        "properties": {
            "product_code": {"type": "string", "description": "Product identifier"},
            "region": {"type": "string", "description": "Inventory region"},
            "requested_quantity": {"type": "integer", "description": "Requested quantity"},
        },
        "required": ["product_code", "region", "requested_quantity"],
        "additionalProperties": False,
    }
    result = ArgumentAdapter().bind(schema, {"product_id": "LAPTOP_001", "region": "US", "quantity": 2})
    assert result == {"product_code": "LAPTOP_001", "region": "US", "requested_quantity": 2}


def test_schema_validator_rejects_missing_required_argument() -> None:
    with pytest.raises(SchemaValidationError):
        validate_arguments(
            {"properties": {"id": {"type": "string"}}, "required": ["id"]},
            {},
        )


def test_schema_validator_rejects_extra_argument() -> None:
    with pytest.raises(SchemaValidationError):
        validate_arguments(
            {"properties": {}, "required": [], "additionalProperties": False},
            {"invented": True},
        )


def test_registry_exposes_no_internal_handler(registry) -> None:
    for tool in registry.openai_tools():
        assert "handler" not in tool
        assert tool["type"] == "function"


def test_schema_validator_supports_nested_objects_and_constraints() -> None:
    schema = {
        "type": "object",
        "properties": {
            "request": {
                "type": "object",
                "properties": {
                    "sku": {"type": "string", "pattern": "^LAPTOP_[0-9]{3}$"},
                    "quantity": {"type": "integer", "minimum": 1, "maximum": 5},
                },
                "required": ["sku", "quantity"],
                "additionalProperties": False,
            }
        },
        "required": ["request"],
        "additionalProperties": False,
    }
    validate_arguments(schema, {"request": {"sku": "LAPTOP_001", "quantity": 2}})
    with pytest.raises(SchemaValidationError):
        validate_arguments(schema, {"request": {"sku": "bad", "quantity": 0}})

