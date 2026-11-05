from __future__ import annotations

import os

import pytest

from ai_shopping_agent.agent import ShoppingAgent
from ai_shopping_agent.audit import AuditLogger
from ai_shopping_agent.config import Settings
from ai_shopping_agent.model_client import OpenAIModelClient


@pytest.mark.live
def test_live_openai_structured_parsing_and_dynamic_tool_loop() -> None:
    if os.getenv("RUN_LIVE_OPENAI_TESTS") != "1":
        pytest.skip("Set RUN_LIVE_OPENAI_TESTS=1 to run paid OpenAI integration tests")
    settings = Settings.from_env()
    if not settings.api_key:
        pytest.skip("OPENAI_API_KEY is not configured")
    client = OpenAIModelClient(
        settings.api_key,
        settings.model,
        settings.timeout_seconds,
        settings.max_retries,
    )
    parsed = client.parse_requirements(
        "I need a laptop under $1,200 with at least 32GB RAM and 1TB SSD storage. "
        "I prefer 10+ hours of battery life and a weight under 1.6kg for software development."
    )
    assert parsed.category == "laptop"
    assert parsed.max_price == 1200
    assert parsed.min_ram_gb == 32
    assert parsed.min_storage_gb == 1024

    tools = [
        {
            "type": "function",
            "name": "inventory_lookup",
            "description": "Look up current regional inventory for a product code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_code": {"type": "string"},
                    "region": {"type": "string"},
                    "requested_quantity": {"type": "integer"},
                },
                "required": ["product_code", "region", "requested_quantity"],
                "additionalProperties": False,
            },
            "strict": True,
        }
    ]
    result = client.run_tool_loop(
        "Use inventory_lookup to check whether one LAPTOP_001 is available in US, then summarize the result.",
        tools,
        lambda _name, arguments: {"available": True, "quantity": 7, **arguments},
        max_steps=4,
    )
    assert result.calls
    assert result.calls[0]["name"] == "inventory_lookup"
    assert result.final_text
    assert result.usage["total_tokens"] > 0


@pytest.mark.live
def test_live_openai_end_to_end_agent_workflow() -> None:
    if os.getenv("RUN_LIVE_OPENAI_TESTS") != "1":
        pytest.skip("Set RUN_LIVE_OPENAI_TESTS=1 to run paid OpenAI integration tests")
    settings = Settings.from_env()
    if not settings.api_key:
        pytest.skip("OPENAI_API_KEY is not configured")
    logger = AuditLogger()
    agent = ShoppingAgent(settings, logger=logger)
    state = agent.run(
        "I need a laptop for software development. My maximum budget is $1,200. "
        "It must have at least 32GB RAM and 1TB SSD storage. I prefer 10+ hours "
        "of battery life and a weight under 1.6kg. Compare the best options and recommend one."
    )
    assert agent.mode == "openai"
    assert state.recommendation.status == "success"
    assert state.recommendation.recommended.product.price <= 1200
    assert state.recommendation.recommended.product.ram_gb >= 32
    assert state.recommendation.recommended.product.storage_gb >= 1024
    assert state.recommendation.recommended.product.availability is True
    assert state.recommendation.comparison_summary
    assert state.model_metrics.get("total_tokens", 0) > 0
    assert any(event["event"] == "model_tool_loop_completed" for event in logger.events)
