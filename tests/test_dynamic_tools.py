from __future__ import annotations

from ai_shopping_agent.agent import ShoppingAgent
from ai_shopping_agent.audit import AuditLogger
from ai_shopping_agent.model_client import SchemaAwareModelClient
from ai_shopping_agent.tools.registry import ToolDefinition
from conftest import SAMPLE_REQUEST


def make_agent(settings, registry, environment) -> ShoppingAgent:
    return ShoppingAgent(
        settings,
        registry=registry,
        environment=environment,
        model_client=SchemaAwareModelClient(),
        logger=AuditLogger(),
    )


def test_adapts_to_unfamiliar_inventory_tool(settings, registry, environment) -> None:
    registry.remove("check_availability")
    registry.register(
        ToolDefinition(
            name="inventory_lookup",
            description="Verify current inventory availability for a product code, region, and requested quantity.",
            handler="availability",
            parameters={
                "type": "object",
                "properties": {
                    "product_code": {"type": "string", "description": "Product identifier or product code."},
                    "region": {"type": "string", "description": "Inventory region."},
                    "requested_quantity": {"type": "integer", "description": "Requested quantity."},
                },
                "required": ["product_code", "region", "requested_quantity"],
                "additionalProperties": False,
            },
        )
    )
    state = make_agent(settings, registry, environment).run(SAMPLE_REQUEST)
    assert state.recommendation.status == "success"
    calls = [record for record in state.tool_calls if record.tool_name == "inventory_lookup"]
    assert calls
    assert set(calls[0].arguments) == {"product_code", "region", "requested_quantity"}


def test_adapts_to_renamed_search_tool_and_parameters(settings, registry, environment) -> None:
    registry.remove("search_products")
    registry.register(
        ToolDefinition(
            name="catalog_query_v2",
            description="Search the product catalog with customer search text, product type, budget, and stock preference.",
            handler="search",
            parameters={
                "type": "object",
                "properties": {
                    "search_text": {"type": "string", "description": "Customer search text or query."},
                    "product_type": {"type": "string", "description": "Requested product category."},
                    "price_ceiling": {"type": "number", "description": "Maximum price ceiling or budget."},
                    "show_out_of_stock": {"type": "boolean", "description": "Whether to include unavailable or out of stock products."},
                },
                "required": ["search_text", "product_type", "price_ceiling", "show_out_of_stock"],
                "additionalProperties": False,
            },
        )
    )
    state = make_agent(settings, registry, environment).run(SAMPLE_REQUEST)
    assert state.recommendation.status == "success"
    call = next(record for record in state.tool_calls if record.tool_name == "catalog_query_v2")
    assert set(call.arguments) == {"search_text", "product_type", "price_ceiling", "show_out_of_stock"}


def test_dynamic_tool_schema_is_presented_to_model(settings, registry, environment) -> None:
    class SpyModel(SchemaAwareModelClient):
        def __init__(self) -> None:
            super().__init__()
            self.seen_tools = []

        def select_tool(self, goal, tools, context):
            self.seen_tools.append(tools)
            return super().select_tool(goal, tools, context)

    spy = SpyModel()
    agent = ShoppingAgent(
        settings,
        registry=registry,
        environment=environment,
        model_client=spy,
        logger=AuditLogger(),
    )
    agent.run(SAMPLE_REQUEST)
    assert spy.seen_tools
    assert all("parameters" in tool for tools in spy.seen_tools for tool in tools)


def test_adapts_to_synonym_only_stock_schema(settings, registry, environment) -> None:
    registry.remove("check_availability")
    registry.register(
        ToolDefinition(
            name="lookup_stock",
            description="Find current product stock by SKU, market code, and units needed.",
            handler="availability",
            parameters={
                "type": "object",
                "properties": {
                    "sku": {"type": "string", "description": "Product SKU."},
                    "market_code": {"type": "string", "description": "Market or region code."},
                    "units_needed": {"type": "integer", "description": "Units or quantity needed."},
                },
                "required": ["sku", "market_code", "units_needed"],
                "additionalProperties": False,
            },
        )
    )
    state = make_agent(settings, registry, environment).run(SAMPLE_REQUEST)
    assert state.recommendation.status == "success"
    calls = [record for record in state.tool_calls if record.tool_name == "lookup_stock"]
    assert calls
    assert set(calls[0].arguments) == {"sku", "market_code", "units_needed"}


def test_adapts_to_nested_inventory_request_schema(settings, registry, environment) -> None:
    registry.remove("check_availability")
    registry.register(
        ToolDefinition(
            name="regional_stock_probe",
            description="Find current inventory stock using a nested request envelope.",
            handler="availability",
            parameters={
                "type": "object",
                "properties": {
                    "request": {
                        "type": "object",
                        "properties": {
                            "sku": {"type": "string", "description": "Product SKU."},
                            "market": {"type": "string", "description": "Inventory market or region."},
                            "units": {"type": "integer", "description": "Units or quantity needed."},
                        },
                        "required": ["sku", "market", "units"],
                        "additionalProperties": False,
                    }
                },
                "required": ["request"],
                "additionalProperties": False,
            },
        )
    )
    state = make_agent(settings, registry, environment).run(SAMPLE_REQUEST)
    assert state.recommendation.status == "success"
    call = next(record for record in state.tool_calls if record.tool_name == "regional_stock_probe")
    assert call.arguments["request"] == {
        "sku": call.arguments["request"]["sku"],
        "market": "US",
        "units": 1,
    }

