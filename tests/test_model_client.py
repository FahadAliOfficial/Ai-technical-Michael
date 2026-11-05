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


def test_openai_tool_loop_returns_tool_output_to_model() -> None:
    client = OpenAIModelClient.__new__(OpenAIModelClient)
    client.model = "gpt-4o-mini"
    call = SimpleNamespace(
        type="function_call",
        name="inventory_lookup",
        arguments='{"product_code":"LAPTOP_001"}',
        call_id="call_123",
    )
    usage = SimpleNamespace(input_tokens=10, output_tokens=5, total_tokens=15)
    responses_to_return = [
        SimpleNamespace(output=[call], output_text="", usage=usage, _request_id="req_1"),
        SimpleNamespace(output=[SimpleNamespace(type="message")], output_text="In stock.", usage=usage, _request_id="req_2"),
    ]

    class Responses:
        def __init__(self):
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            return responses_to_return.pop(0)

    responses = Responses()
    client.client = SimpleNamespace(responses=responses)
    tools = [
        {
            "type": "function",
            "name": "inventory_lookup",
            "description": "Look up inventory",
            "parameters": {
                "type": "object",
                "properties": {"product_code": {"type": "string"}},
                "required": ["product_code"],
                "additionalProperties": False,
            },
            "strict": True,
        }
    ]
    result = client.run_tool_loop(
        "Check stock",
        tools,
        lambda name, arguments: {"available": name == "inventory_lookup", **arguments},
    )
    assert result.final_text == "In stock."
    assert result.steps == 2
    assert result.usage["total_tokens"] == 30
    assert result.calls[0]["result"]["available"] is True
    continuation = responses.calls[1]["input"]
    assert any(isinstance(item, dict) and item.get("type") == "function_call_output" for item in continuation)
    assert responses.calls[0]["tool_choice"] == "required"
    assert responses.calls[1]["tool_choice"] == "auto"

