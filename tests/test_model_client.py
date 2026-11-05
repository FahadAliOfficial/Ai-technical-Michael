from __future__ import annotations

from types import SimpleNamespace

from ai_shopping_agent.model_client import OpenAIModelClient


def test_openai_client_sends_runtime_tools_and_uses_returned_arguments() -> None:
    client = OpenAIModelClient.__new__(OpenAIModelClient)
    client.model = "gpt-4o-mini"
    function_call = SimpleNamespace(type="function_call", name="inventory_lookup", arguments='{"code":"LAPTOP_001"}')

    class Responses:
        def create(self, **kwargs):
            self.kwargs = kwargs
            return SimpleNamespace(output=[function_call])

    responses = Responses()
    client.client = SimpleNamespace(responses=responses)
    tools = [
        {
            "type": "function",
            "name": "inventory_lookup",
            "description": "Look up inventory",
            "parameters": {
                "type": "object",
                "properties": {"code": {"type": "string"}},
                "required": ["code"],
                "additionalProperties": False,
            },
            "strict": True,
        }
    ]
    name, arguments = client.select_tool("check stock", tools, {"product_id": "LAPTOP_001"})
    assert name == "inventory_lookup"
    assert arguments == {"code": "LAPTOP_001"}
    assert responses.kwargs["tools"] == tools
    assert responses.kwargs["tool_choice"] == "required"

