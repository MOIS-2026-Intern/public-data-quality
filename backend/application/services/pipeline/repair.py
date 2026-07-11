from __future__ import annotations

from backend.application.dto import (
    PipelineState,
    merge_state_updates,
    pipeline_data,
    pipeline_result,
    update_pipeline_data,
    update_pipeline_result,
)
from backend.config.pipeline import REPAIR_STEP_NAME
from backend.domain.services.validation import build_repair_suggestion
from .tracing import pipeline_trace


def propose_repairs(state: PipelineState) -> PipelineState:
    data = pipeline_data(state)
    traces = list(pipeline_result(state).agent_traces)
    updated = []
    for column in data.columns:
        column.repair_suggestion = build_repair_suggestion(column)
        traces.append(
            pipeline_trace(
                REPAIR_STEP_NAME,
                action="propose_repair",
                target=column.raw_name,
                detail=column.repair_suggestion or "none",
            )
        )
        updated.append(column)
    return merge_state_updates(
        update_pipeline_data(state, columns=updated),
        update_pipeline_result(state, agent_traces=traces),
    )
