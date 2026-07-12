from __future__ import annotations

from backend.application.dto import (
    PipelineState,
    merge_state_updates,
    pipeline_data,
    pipeline_request,
    pipeline_result,
    update_pipeline_data,
    update_pipeline_result,
)
from backend.application.agents.base import BaseAgent
from backend.application.services.resolution.semantic_profiler import LLMSemanticProfiler
from backend.domain.policies.columns import semantic_profile_llm_reasons


class SemanticProfilingAgent(BaseAgent):
    name = "semantic_profiler"

    def __init__(self, semantic_profiler: LLMSemanticProfiler | None = None):
        self.semantic_profiler = semantic_profiler

    def _llm_debug_detail(self, use_llm: bool, llm_attempted: bool) -> tuple[str, str]:
        if not use_llm or not llm_attempted or self.semantic_profiler is None:
            return "", ""
        return self.semantic_profiler.last_error, self.semantic_profiler.last_response_preview

    def run(self, state: PipelineState) -> PipelineState:
        traces = list(pipeline_result(state).agent_traces)
        data = pipeline_data(state)
        request = pipeline_request(state)
        updated = []
        use_llm = (
            request.use_llm_agents
            and self.semantic_profiler is not None
            and self.semantic_profiler.enabled
        )

        for column in data.columns:
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

        return merge_state_updates(
            update_pipeline_data(state, columns=updated),
            update_pipeline_result(state, agent_traces=traces),
        )
