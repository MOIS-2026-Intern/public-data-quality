from __future__ import annotations

from backend.application.dto import (
    PipelineState,
    merge_state_updates,
    pipeline_data,
    pipeline_result,
    pipeline_rows,
    require_dataset_meta,
    update_pipeline_result,
)
from backend.config.pipeline import VALIDATION_STEP_NAME
from backend.domain.entities.models import ValidationFinding
from backend.domain.services.validation import validate_column, validate_dataset_relationships
from .tracing import pipeline_trace


def validate_quality(state: PipelineState) -> PipelineState:
    data = pipeline_data(state)
    result = pipeline_result(state)
    dataset_meta = require_dataset_meta(state)
    findings: list[ValidationFinding] = []
    traces = list(result.agent_traces)
    validation_rows = pipeline_rows(state)

    for column in data.columns:
        column_findings = validate_column(column, dataset_meta, validation_rows)
        findings.extend(column_findings)
        traces.append(
            pipeline_trace(
                VALIDATION_STEP_NAME,
                action="validate_column",
                target=column.raw_name,
                detail=f"findings={len(column_findings)}",
            )
        )

    relationship_findings = validate_dataset_relationships(
        data.columns,
        validation_rows,
        data.relationship_candidates,
    )
    findings.extend(relationship_findings)
    traces.append(
        pipeline_trace(
            VALIDATION_STEP_NAME,
            action="validate_relationships",
            target=dataset_meta.dataset_id,
            detail=(
                f"findings={len(relationship_findings)}, "
                f"candidates={len(data.relationship_candidates)}"
            ),
        )
    )

    return update_pipeline_result(state, findings=findings, agent_traces=traces)
