from __future__ import annotations

import json
import re
from typing import Any

from openai import OpenAI

from .models import Requirements
from .parser import RuleBasedRequirementParser
from .tools.adapter import ArgumentAdapter, validate_arguments


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
        wanted = set(re.findall(r"[a-z0-9]+", goal.lower()))
        scored = []
        for tool in tools:
            haystack = f"{tool['name']} {tool['description']}".lower().replace("_", " ")
            scored.append((len(wanted & set(re.findall(r"[a-z0-9]+", haystack))), tool))
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

    def parse_requirements(self, request: str, previous: Requirements | None = None) -> Requirements:
        previous_text = previous.model_dump_json() if previous else "null"
        response = self.client.responses.parse(
            model=self.model,
            instructions=(
                "Extract shopping requirements. Separate mandatory constraints from preferences. "
                "Preserve previous values unless the new request changes them. Identify contradictions "
                "and ask one targeted clarification question. Storage is expressed in GB; one TB is 1024 GB."
            ),
            input=f"Previous requirements: {previous_text}\nCustomer request: {request}",
            text_format=Requirements,
            store=False,
        )
        parsed = response.output_parsed
        if parsed is None:
            raise ValueError("The model did not return structured requirements")
        return parsed

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
        for item in response.output:
            if getattr(item, "type", None) == "function_call":
                arguments = json.loads(item.arguments)
                selected = next(tool for tool in tools if tool["name"] == item.name)
                validate_arguments(selected["parameters"], arguments)
                return item.name, arguments
        raise ValueError("The model did not select a tool")

