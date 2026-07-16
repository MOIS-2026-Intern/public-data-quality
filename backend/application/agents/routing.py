from __future__ import annotations

from typing import TYPE_CHECKING, Any

from backend.application.agents.base import BaseAgent
from backend.application.dto import (
    PipelineState,
    merge_state_updates,
    pipeline_data,
    pipeline_request,
    pipeline_result,
    update_pipeline_data,
    update_pipeline_result,
)
from backend.application.services.resolution.rule_routing import apply_llm_route, apply_rule_fallback
from backend.domain.entities.models import ColumnProfile

if TYPE_CHECKING:
    from backend.application.services.resolution.column_resolver import LLMColumnResolver


def _needs_llm_route(column: ColumnProfile) -> bool:
    if column.semantic_tags == ["free_text"]:
        return False
    return not bool(column.assigned_rules)


class LLMRoutingAgent(BaseAgent):
    name = "rule_router"

    def __init__(self, column_resolver: "LLMColumnResolver | None" = None):
        self.column_resolver = column_resolver

    def _trace_routed_column(
        self,
        *,
        traces: list,
        column: ColumnProfile,
        route_source: str,
        llm_error: str,
        llm_model: str,
        llm_stage: str,
        llm_escalated: str,
    ) -> None:
        traces.append(
            self.trace(
                action="route_rules",
                target=column.raw_name,
                detail=(
                    f"source={route_source}, "
                    f"rules={column.assigned_rules}, "
                    f"confidence={column.routing_confidence:.2f}, "
                    f"model={llm_model}, stage={llm_stage}, escalated={llm_escalated}, "
                    f"llm_error={llm_error}"
                ),
            )
        )

    def _resolve_relationship_candidates(
        self,
        *,
        state: PipelineState,
        columns: list[ColumnProfile],
        use_llm: bool,
        traces: list,
    ) -> list[dict[str, object]] | None:
        if not use_llm:
            return None

        relationship_candidates = self.column_resolver.resolve_relationships(state, columns)
        traces.append(
            self.trace(
                action="route_relationships",
                detail=(
                    f"candidates={len(relationship_candidates)}, "
                    f"model={self.column_resolver.last_model_name}, "
                    f"stage={self.column_resolver.last_stage}, "
                    f"llm_error={self.column_resolver.last_error}"
                ),
            )
        )
        return relationship_candidates

    def run(self, state: PipelineState) -> PipelineState:
        request = pipeline_request(state)
        data = pipeline_data(state)
        traces = list(pipeline_result(state).agent_traces)
        updated: list[ColumnProfile] = []
        use_llm = (
            request.use_llm_agents
            and self.column_resolver is not None
            and self.column_resolver.enabled
        )
        fallback_columns = [apply_rule_fallback(column) for column in data.columns]
        llm_targets = [column for column in fallback_columns if use_llm and _needs_llm_route(column)]
        resolved_payloads = self.column_resolver.resolve_many(state, llm_targets) if llm_targets else {}
        relationship_candidates: list[dict[str, Any]] | None = None

        for column in fallback_columns:
            route_source = "rule_fallback"
            llm_error = ""
            llm_model = ""
            llm_stage = ""
            llm_escalated = ""
            payload = resolved_payloads.get(column.raw_name)
            if use_llm and payload:
                column = apply_llm_route(column, payload)
                route_source = f"llm:{payload.get('_llm_stage', 'fast')}"
                llm_model = str(payload.get("_llm_model", ""))
                llm_stage = str(payload.get("_llm_stage", ""))
                llm_escalated = str(payload.get("_llm_escalated", ""))
            elif use_llm and _needs_llm_route(column):
                llm_error = self.column_resolver.last_error
                llm_model = getattr(self.column_resolver, "last_model_name", "")
                llm_stage = getattr(self.column_resolver, "last_stage", "")
            self._trace_routed_column(
                traces=traces,
                column=column,
                route_source=route_source,
                llm_error=llm_error,
                llm_model=llm_model,
                llm_stage=llm_stage,
                llm_escalated=llm_escalated,
            )
            updated.append(column)

        relationship_candidates = self._resolve_relationship_candidates(
            state=state,
            columns=updated,
            use_llm=use_llm,
            traces=traces,
        )

        traces.append(self.trace(action="routing_summary", detail=f"columns={len(updated)}"))
        result: PipelineState = merge_state_updates(
            update_pipeline_data(state, columns=updated),
            update_pipeline_result(state, agent_traces=traces),
        )
        if relationship_candidates is not None:
            result.update(update_pipeline_data(state, columns=updated, relationship_candidates=relationship_candidates))
        return result
