from __future__ import annotations

try:
    from backend.application.dto.pipeline import AgentTrace
except ImportError:  # pragma: no cover
    if (__package__ or "").split(".", 1)[0] != "services":
        raise
    from backend.application.dto.pipeline import AgentTrace


class BaseAgent:
    name = "base_agent"

    def trace(self, action: str, target: str | None = None, detail: str = "") -> AgentTrace:
        return AgentTrace(agent_name=self.name, action=action, target=target, detail=detail)
