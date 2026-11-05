from __future__ import annotations

from .models import AgentState, Requirements


class StateManager:
    def new(self, request: str, requirements: Requirements) -> AgentState:
        return AgentState(raw_request=request, requirements=requirements)

    def update(self, state: AgentState, request: str, requirements: Requirements) -> AgentState:
        state.apply_request_update(request, requirements)
        return state

