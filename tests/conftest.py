from __future__ import annotations

from pathlib import Path

import pytest

from ai_shopping_agent.agent import ShoppingAgent
from ai_shopping_agent.audit import AuditLogger
from ai_shopping_agent.config import Settings
from ai_shopping_agent.model_client import SchemaAwareModelClient
from ai_shopping_agent.tools.mock_tools import MockToolEnvironment
from ai_shopping_agent.tools.registry import ToolRegistry


SAMPLE_REQUEST = (
    "I need a laptop for software development. My maximum budget is $1,200. "
    "It must have at least 32GB RAM and 1TB SSD storage. I prefer 10+ hours "
    "of battery life and a weight under 1.6kg. Compare the best options and recommend one."
)


@pytest.fixture
def settings() -> Settings:
    return Settings(log_path=Path("logs/test-agent.jsonl"))


@pytest.fixture
def registry(settings: Settings) -> ToolRegistry:
    return ToolRegistry.from_file(settings.tool_manifest_path)


@pytest.fixture
def environment(settings: Settings) -> MockToolEnvironment:
    return MockToolEnvironment(settings.catalog_path, settings.inventory_path, settings.reviews_path)


@pytest.fixture
def agent(settings: Settings, registry: ToolRegistry, environment: MockToolEnvironment) -> ShoppingAgent:
    return ShoppingAgent(
        settings,
        registry=registry,
        environment=environment,
        model_client=SchemaAwareModelClient(),
        logger=AuditLogger(),
    )

