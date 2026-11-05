from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from openai import OpenAI

from .models import Requirements
from .parser import RuleBasedRequirementParser
from .tools.adapter import ArgumentAdapter, validate_arguments
from .tools.registry import tool_match_score


@dataclass(slots=True)
class ToolLoopResult:
    final_text: str
    steps: int
    calls: list[dict[str, Any]] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)
    request_ids: list[str] = field(default_factory=list)


class SchemaAwareModelClient:
    """Offline model substitute used for repeatable tests and no-key demos."""

    def __init__(self) -> None:
        self.parser = RuleBasedRequirementParser()
        self.adapter = ArgumentAdapter()

    def parse_requirements(self, request: str, previous: Requirements | None = None) -> Requirements:
        return self.parser.parse(request, previous)

    def select_tool(
        self,
        goal: str,
        tools: list[dict[str, Any]],
        context: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        scored = []
        for tool in tools:
            scored.append(
                (
                    tool_match_score(goal, tool["name"], tool["description"], tool["parameters"]),
                    tool,
                )
            )
        score, selected = max(scored, key=lambda item: item[0])
        if score == 0:
            raise LookupError(f"No supplied tool matches goal: {goal}")
        arguments = self.adapter.bind(selected["parameters"], context)
        return selected["name"], arguments


class OpenAIModelClient:
    """Thin Responses API adapter; domain decisions remain outside the model."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
    ) -> None:
        self.model = model
        self.client = OpenAI(api_key=api_key, timeout=timeout_seconds, max_retries=max_retries)
        self.usage_totals = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        self.request_ids: list[str] = []

    def _record_response(self, response: Any) -> None:
        if not hasattr(self, "usage_totals"):
            self.usage_totals = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        if not hasattr(self, "request_ids"):
            self.request_ids = []
        request_id = getattr(response, "_request_id", None)
        if request_id:
            self.request_ids.append(request_id)
        response_usage = getattr(response, "usage", None)
        if response_usage:
            for key in self.usage_totals:
                self.usage_totals[key] += int(getattr(response_usage, key, 0) or 0)

    def parse_requirements(self, request: str, previous: Requirements | None = None) -> Requirements:
        previous_text = previous.model_dump_json() if previous else "null"
        response = self.client.responses.parse(
            model=self.model,
            instructions=(
                "Extract shopping requirements. Separate mandatory constraints from preferences. "
                "Preserve previous values unless the new request changes them. Identify contradictions "
                "and ask one targeted clarification question. Storage is expressed in GB; one TB is 1024 GB. "
                "Category means the physical product type (for example, laptop). Purpose means the use case "
                "(for example, software development). Never place the use case in category."
            ),
            input=f"Previous requirements: {previous_text}\nCustomer request: {request}",
            text_format=Requirements,
            store=False,
        )
        self._record_response(response)
        parsed = response.output_parsed
        if parsed is None:
            raise ValueError("The model did not return structured requirements")
        return parsed.model_copy(
            update={
                "category": parsed.category.lower().strip() if parsed.category else None,
                "storage_type": parsed.storage_type.upper().strip() if parsed.storage_type else None,
                "purpose": parsed.purpose.lower().strip() if parsed.purpose else None,
            }
        )

    def select_tool(
        self,
        goal: str,
        tools: list[dict[str, Any]],
        context: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        response = self.client.responses.create(
            model=self.model,
            instructions=(
                "Select exactly one supplied function that accomplishes the goal. Inspect its current "
                "name and parameter schema; never assume an older tool name or parameter."
            ),
            input=f"Goal: {goal}\nAvailable context: {json.dumps(context, sort_keys=True)}",
            tools=tools,
            tool_choice="required",
            parallel_tool_calls=False,
            store=False,
        )
        self._record_response(response)
        for item in response.output:
            if getattr(item, "type", None) == "function_call":
                arguments = json.loads(item.arguments)
                selected = next(tool for tool in tools if tool["name"] == item.name)
                validate_arguments(selected["parameters"], arguments)
                return item.name, arguments
        raise ValueError("The model did not select a tool")

    def run_tool_loop(
        self,
        prompt: str,
        tools: list[dict[str, Any]],
        execute: Any,
        *,
        max_steps: int = 8,
    ) -> ToolLoopResult:
        """Run a stateless Responses function-call loop and return the grounded final text."""
        input_items: list[Any] = [{"role": "user", "content": prompt}]
        calls: list[dict[str, Any]] = []
        usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        request_ids: list[str] = []

        for step in range(1, max_steps + 1):
            response = self.client.responses.create(
                model=self.model,
                instructions=(
                    "Use the supplied tools to inspect the verified candidates before answering. "
                    "Treat the supplied mandatory-valid candidate list as authoritative: do not add a different product. "
                    "Explain the recommendation and alternatives using only tool results and supplied facts."
                ),
                input=input_items,
                tools=tools,
                tool_choice="required" if step == 1 else "auto",
                parallel_tool_calls=False,
                store=False,
            )
            self._record_response(response)
            request_id = getattr(response, "_request_id", None)
            if request_id:
                request_ids.append(request_id)
            response_usage = getattr(response, "usage", None)
            if response_usage:
                for key in usage:
                    usage[key] += int(getattr(response_usage, key, 0) or 0)

            output_items = list(response.output)
            input_items.extend(output_items)
            function_calls = [item for item in output_items if getattr(item, "type", None) == "function_call"]
            if not function_calls:
                final_text = (response.output_text or "").strip()
                if not final_text:
                    raise ValueError("The model ended the tool loop without a final explanation")
                return ToolLoopResult(
                    final_text=final_text,
                    steps=step,
                    calls=calls,
                    usage=usage,
                    request_ids=request_ids,
                )

            for call in function_calls:
                selected = next((tool for tool in tools if tool["name"] == call.name), None)
                if selected is None:
                    raise ValueError(f"The model selected unknown tool {call.name!r}")
                arguments = json.loads(call.arguments)
                validate_arguments(selected["parameters"], arguments)
                result = execute(call.name, arguments)
                calls.append(
                    {
                        "name": call.name,
                        "arguments": arguments,
                        "call_id": call.call_id,
                        "result": result,
                    }
                )
                input_items.append(
                    {
                        "type": "function_call_output",
                        "call_id": call.call_id,
                        "output": json.dumps(result, sort_keys=True),
                    }
                )

        raise RuntimeError(f"Tool loop exceeded the maximum of {max_steps} model steps")

