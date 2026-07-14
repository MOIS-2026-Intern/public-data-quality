from __future__ import annotations

from typing import Any

from backend.config.pipeline import PIPELINE_DATASET_META_TYPE_ERROR
from backend.domain.entities.models import DatasetMeta

from .pipeline_models import PipelineData, PipelineDataState, PipelineRequest, PipelineRequestState, PipelineResult, PipelineResultState


def request_state_payload(request: PipelineRequest) -> PipelineRequestState:
    return {
        "meta_csv_path": request.meta_csv_path,
        "uploaded_dataset_path": request.uploaded_dataset_path,
        "uploaded_dataset_name": request.uploaded_dataset_name,
        "use_llm_agents": request.use_llm_agents,
        "llm_model": request.llm_model,
        "llm_fast_model": request.llm_fast_model,
        "llm_strong_model": request.llm_strong_model,
        "dataset_id": request.dataset_id,
        "dataset_name": request.dataset_name,
    }


def data_state_payload(data: PipelineData) -> PipelineDataState:
    return {
        "dataset_meta": data.dataset_meta,
        "preview_headers": data.preview_headers,
        "preview_rows": data.preview_rows,
        "validation_rows": data.validation_rows,
        "relationship_candidates": data.relationship_candidates,
        "columns": data.columns,
    }


def result_state_payload(result: PipelineResult) -> PipelineResultState:
    return {"findings": result.findings, "agent_traces": result.agent_traces, "summary": result.summary}


def dataset_meta_value(value: Any) -> DatasetMeta | None:
    if value is None:
        return None
    if not isinstance(value, DatasetMeta):
        raise TypeError(PIPELINE_DATASET_META_TYPE_ERROR)
    return value


def stringify_cell_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def is_string_row_list(value: list[Any]) -> bool:
    return all(
        isinstance(item, dict)
        and all(isinstance(key, str) and isinstance(nested_value, str) for key, nested_value in item.items())
        for item in value
    )
