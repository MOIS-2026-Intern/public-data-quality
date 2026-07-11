from __future__ import annotations

from backend.application.dto.pipeline import PipelineState
from backend.application.services.agent_base import BaseAgent
from backend.application.services.resolution.semantic_profiler import LLMSemanticProfiler
from backend.domain.policies import semantic_profile_llm_reasons


class SemanticProfilingAgent(BaseAgent):
    name = "semantic_profiler"

    def __init__(self, semantic_profiler: LLMSemanticProfiler | None = None):
        self.semantic_profiler = semantic_profiler

    def _llm_debug_detail(self, use_llm: bool, llm_attempted: bool) -> tuple[str, str]:
        if not use_llm or not llm_attempted or self.semantic_profiler is None:
            return "", ""
        return self.semantic_profiler.last_error, self.semantic_profiler.last_response_preview

    def run(self, state: PipelineState) -> PipelineState:
        traces = list(state.get("agent_traces", []))
        updated = []
        use_llm = bool(state.get("use_llm_agents")) and self.semantic_profiler is not None

        for column in state["columns"]:
            llm_reasons = semantic_profile_llm_reasons(column)
            needs_llm = use_llm and bool(llm_reasons)
            llm_attempted = False
            column.semantic_profile_llm_needed = needs_llm
            column.semantic_profile_llm_reasons = llm_reasons
            if needs_llm:
                llm_attempted = True
                profile = self.semantic_profiler.profile(state, column)
                if profile:
                    column.semantic_profile_label = profile.get("label")
                    column.semantic_profile_description = profile.get("description")
                    column.semantic_profile_confidence = profile.get("confidence")
            llm_error, llm_preview = self._llm_debug_detail(use_llm, llm_attempted)
            traces.append(
                self.trace(
                    action="semantic_profile",
                    target=column.raw_name,
                    detail=(
                        f"label={column.semantic_profile_label}, "
                        f"confidence={column.semantic_profile_confidence}, "
                        f"llm_needed={needs_llm}, reasons={llm_reasons}, "
                        f"model={getattr(self.semantic_profiler, 'last_model_name', '')}, "
                        f"stage={getattr(self.semantic_profiler, 'last_stage', '')}, "
                        f"llm_error={llm_error}, "
                        f"llm_preview={llm_preview}"
                    ),
                )
            )
            updated.append(column)

        return {"columns": updated, "agent_traces": traces}
