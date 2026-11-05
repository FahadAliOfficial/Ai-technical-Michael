from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict


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
        stop = {"a", "an", "and", "for", "of", "the", "to", "using", "with"}
        wanted = {token for token in re.findall(r"[a-z0-9]+", goal.lower()) if token not in stop}
        best: tuple[int, ToolDefinition] | None = None
        for tool in self._tools.values():
            haystack = f"{tool.name} {tool.description}".lower().replace("_", " ")
            available = set(re.findall(r"[a-z0-9]+", haystack))
            score = len(wanted & available)
            if best is None or score > best[0]:
                best = (score, tool)
        if best is None or best[0] == 0:
            raise LookupError(f"No tool matches goal: {goal}")
        return best[1]

