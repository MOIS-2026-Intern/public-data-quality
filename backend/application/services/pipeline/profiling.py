from __future__ import annotations

from backend.application.ports import DatasetGatewayPort
from backend.application.dto import AgentTrace, PipelineState, merge_state_updates, pipeline_data, pipeline_request, pipeline_result, require_dataset_meta, update_pipeline_data, update_pipeline_result
from backend.config.pipeline import PROFILE_STEP_NAME
from backend.config.profiling import (
    PROFILE_SAMPLE_ROW_LIMIT,
    PROFILE_UPLOADED_ROW_BUFFER_SIZE,
)
from backend.domain.entities.models import ColumnProfile
from .profiling_metadata import apply_column_metadata as _apply_column_metadata, column_metadata_row as _column_metadata_row
from .profiling_stats import apply_profile_stats as _apply_profile_stats, initial_profile_stats as _initial_profile_stats, update_profile_stats as _update_profile_stats
from .tracing import pipeline_trace

ProfileStats = dict[str, dict]


def profile_values(
    state: PipelineState,
    *,
    dataset_gateway: DatasetGatewayPort | None = None,
) -> PipelineState:
    request = pipeline_request(state)
    data = pipeline_data(state)
    traces = list(pipeline_result(state).agent_traces)
    uploaded_path = request.uploaded_dataset_path
    if not uploaded_path:
        traces.append(
            pipeline_trace(
                PROFILE_STEP_NAME,
                action="profile_values",
                detail="skipped:no_uploaded_dataset",
            )
        )
        return merge_state_updates(
            update_pipeline_data(state, columns=data.columns),
            update_pipeline_result(state, agent_traces=traces),
        )

    columns_by_name = {column.raw_name: column for column in data.columns}
    preview_rows: list[dict[str, str]] = []
    validation_rows: list[dict[str, str]] = []
    stats = _initial_profile_stats(columns_by_name)

    if dataset_gateway is None:
        raise ValueError("dataset_gateway is required to profile uploaded rows.")

    uploaded_rows = dataset_gateway.iter_uploaded_rows(uploaded_path)
    buffered_rows = _buffered_uploaded_rows(uploaded_rows)
    metadata_row = _column_metadata_row(columns_by_name, buffered_rows)
    if metadata_row:
        _apply_column_metadata(columns_by_name, metadata_row)
        traces.append(
            pipeline_trace(
                PROFILE_STEP_NAME,
                action="detect_column_metadata_row",
                detail="row=2; skipped_from_validation=true",
            )
        )

    for row in _iter_profile_rows(uploaded_rows, buffered_rows, skip_first=bool(metadata_row)):
        validation_rows.append(row)
        if len(preview_rows) < PROFILE_SAMPLE_ROW_LIMIT:
            preview_rows.append(row)
        _update_profile_stats(row, columns_by_name, stats)

    updated = _apply_profile_stats(columns_by_name, stats, traces)
    dataset_meta = require_dataset_meta(state)
    if updated:
        dataset_meta.total_rows = stats[updated[0].raw_name]["rows"]

    return merge_state_updates(
        update_pipeline_data(
            state,
            columns=updated,
            preview_headers=list(columns_by_name.keys()),
            preview_rows=preview_rows,
            validation_rows=validation_rows,
            dataset_meta=dataset_meta,
        ),
        update_pipeline_result(state, agent_traces=traces),
    )


def _buffered_uploaded_rows(
    uploaded_rows,
    *,
    sample_size: int = PROFILE_UPLOADED_ROW_BUFFER_SIZE,
) -> list[dict[str, str]]:
    buffered_rows: list[dict[str, str]] = []
    for row in uploaded_rows:
        buffered_rows.append(_normalize_uploaded_row(row))
        if len(buffered_rows) >= sample_size:
            break
    return buffered_rows


def _iter_profile_rows(
    uploaded_rows,
    buffered_rows: list[dict[str, str]],
    *,
    skip_first: bool,
):
    start_index = 1 if skip_first else 0
    for row in buffered_rows[start_index:]:
        yield row
    for row in uploaded_rows:
        yield _normalize_uploaded_row(row)


def _normalize_uploaded_row(row: dict[object, object]) -> dict[str, str]:
    return {str(key): _stringify_cell_value(value) for key, value in row.items()}


def _stringify_cell_value(value: object) -> str:
    if value is None:
        return ""
    return str(value)
