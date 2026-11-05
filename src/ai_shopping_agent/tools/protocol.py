from __future__ import annotations

from typing import Any, Protocol

from ..models import AgentState, Requirements


class ToolPlanner(Protocol):
    def select_tool(
        self,
        goal: str,
        tools: list[dict[str, Any]],
        context: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]: ...


class RequirementParser(Protocol):
    def parse(self, request: str, previous: Requirements | None = None) -> Requirements: ...


class AgentObserver(Protocol):
    def on_state(self, state: AgentState) -> None: ...

