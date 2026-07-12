from __future__ import annotations

from backend.application.dto.pipeline import AgentTrace


class BaseAgent:
    name = "base_agent"

    def trace(self, action: str, target: str | None = None, detail: str = "") -> AgentTrace:
        return AgentTrace(agent_name=self.name, action=action, target=target, detail=detail)
