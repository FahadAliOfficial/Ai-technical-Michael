from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from .adapter import semantic_role


_SYNONYM_GROUPS = (
    {"availability", "inventory", "stock"},
    {"search", "find", "query", "catalog"},
    {"details", "specifications", "specs", "inspect"},
    {"compare", "comparison", "contrast"},
    {"reviews", "review", "feedback", "ratings", "rating"},
    {"product", "item", "sku"},
)


def semantic_tokens(text: str) -> set[str]:
    tokens = set(re.findall(r"[a-z0-9]+", text.lower().replace("_", " ")))
    expanded = set(tokens)
    for group in _SYNONYM_GROUPS:
        if tokens & group:
            expanded.update(group)
    return expanded


def tool_match_score(
    goal: str,
    name: str,
    description: str,
    parameters: dict[str, Any],
) -> int:
    wanted = semantic_tokens(goal)
    available = semantic_tokens(f"{name} {description}")
    score = len(wanted & available)
    properties = parameters.get("properties", {})
    roles = {semantic_role(key, value) for key, value in properties.items()}

    if wanted & {"availability", "inventory", "stock"}:
        score += 10 if "product_id" in roles and "query" not in roles else -5
    if wanted & {"search", "find", "query", "catalog"}:
        score += 10 if "query" in roles else 0
    if wanted & {"compare", "comparison", "contrast"}:
        score += 10 if "product_ids" in roles else 0
    if wanted & {"details", "specifications", "specs", "inspect"}:
        score += 5 if roles == {"product_id"} else 0
    if wanted & {"reviews", "review", "feedback", "ratings", "rating"}:
        score += 5 if roles == {"product_id"} else 0
    return score


class ToolDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    description: str
    parameters: dict[str, Any]
    handler: str

    def as_openai_tool(self) -> dict[str, Any]:
        return {
            "type": "function",
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "strict": True,
        }


class ToolRegistry:
    def __init__(self, tools: list[ToolDefinition]) -> None:
        self._tools = {tool.name: tool for tool in tools}

    @classmethod
    def from_file(cls, path: str | Path) -> "ToolRegistry":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls([ToolDefinition.model_validate(item) for item in payload])

    def list(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    def openai_tools(self) -> list[dict[str, Any]]:
        return [tool.as_openai_tool() for tool in self.list()]

    def get(self, name: str) -> ToolDefinition:
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}")
        return self._tools[name]

    def register(self, tool: ToolDefinition) -> None:
        self._tools[tool.name] = tool

    def remove(self, name: str) -> None:
        self._tools.pop(name, None)

    def find(self, goal: str) -> ToolDefinition:
        best: tuple[int, ToolDefinition] | None = None
        for tool in self._tools.values():
            score = tool_match_score(goal, tool.name, tool.description, tool.parameters)
            if best is None or score > best[0]:
                best = (score, tool)
        if best is None or best[0] == 0:
            raise LookupError(f"No tool matches goal: {goal}")
        return best[1]

