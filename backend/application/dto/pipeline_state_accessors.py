from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Callable, cast

from backend.config.common import EMPTY_TEXT_VALUES
from backend.config.pipeline import (
    PIPELINE_AGENT_TRACES_ITEM_TYPE_ERROR,
    PIPELINE_AGENT_TRACES_TYPE_ERROR,
    PIPELINE_COLUMNS_ITEM_TYPE_ERROR,
    PIPELINE_COLUMNS_TYPE_ERROR,
    PIPELINE_DATASET_META_REQUIRED_ERROR,
    PIPELINE_DICT_LIST_ITEM_TYPE_ERROR,
    PIPELINE_DICT_LIST_TYPE_ERROR,
    PIPELINE_DICT_TYPE_ERROR,
    PIPELINE_FINDINGS_ITEM_TYPE_ERROR,
    PIPELINE_FINDINGS_TYPE_ERROR,
    PIPELINE_REQUEST_BOOL_TYPE_ERROR,
    PIPELINE_REQUEST_TEXT_TYPE_ERROR,
    PIPELINE_ROW_LIST_ITEM_TYPE_ERROR,
    PIPELINE_ROW_LIST_TYPE_ERROR,
    PIPELINE_STRING_LIST_ITEM_TYPE_ERROR,
    PIPELINE_STRING_LIST_TYPE_ERROR,
    PIPELINE_UNKNOWN_FIELD_ERROR,
)
from backend.domain.entities.models import ColumnProfile, DatasetMeta, ValidationFinding

from .pipeline_models import (
    AgentTrace,
    PipelineData,
    PipelineDataState,
    PipelineRequest,
    PipelineRequestState,
    PipelineResult,
    PipelineResultState,
    PipelineState,
)
from .pipeline_state_helpers import (
    data_state_payload as _data_state_payload,
    dataset_meta_value as _dataset_meta_value,
    is_string_row_list as _is_string_row_list,
    request_state_payload as _request_state_payload,
    result_state_payload as _result_state_payload,
    stringify_cell_value as _stringify_cell_value,
)


def pipeline_request(state: Mapping[str, Any]) -> PipelineRequest:
    return PipelineRequest(
        meta_csv_path=_optional_text("meta_csv_path", state.get("meta_csv_path")),
        uploaded_dataset_path=_optional_text("uploaded_dataset_path", state.get("uploaded_dataset_path")),
        uploaded_dataset_name=_optional_text("uploaded_dataset_name", state.get("uploaded_dataset_name")),
        use_llm_agents=_bool_value("use_llm_agents", state.get("use_llm_agents")),
        llm_model=_optional_text("llm_model", state.get("llm_model")),
        llm_fast_model=_optional_text("llm_fast_model", state.get("llm_fast_model")),
        llm_strong_model=_optional_text("llm_strong_model", state.get("llm_strong_model")),
        dataset_id=_optional_text("dataset_id", state.get("dataset_id")),
        dataset_name=_optional_text("dataset_name", state.get("dataset_name")),
    )


def pipeline_data(state: Mapping[str, Any]) -> PipelineData:
    return PipelineData.model_construct(
        dataset_meta=_dataset_meta_value(state.get("dataset_meta")),
        preview_headers=_string_list("preview_headers", state.get("preview_headers")),
        preview_rows=_row_list("preview_rows", state.get("preview_rows")),
        validation_rows=_row_list("validation_rows", state.get("validation_rows")),
        relationship_candidates=_dict_list("relationship_candidates", state.get("relationship_candidates")),
        columns=_column_list(state.get("columns")),
    )


def pipeline_result(state: Mapping[str, Any]) -> PipelineResult:
    return PipelineResult.model_construct(
        findings=_finding_list(state.get("findings")),
        agent_traces=_trace_list(state.get("agent_traces")),
        summary=_dict_value("summary", state.get("summary")),
    )


def pipeline_rows(state: Mapping[str, Any]) -> list[dict[str, str]]:
    validation_rows = _row_list("validation_rows", state.get("validation_rows"))
    return validation_rows or _row_list("preview_rows", state.get("preview_rows"))


def pipeline_state_update(
    *,
    request: PipelineRequest | None = None,
    data: PipelineData | None = None,
    result: PipelineResult | None = None,
) -> PipelineState:
    payload: PipelineState = {}
    if request is not None:
        payload.update(_request_state_payload(request))
    if data is not None:
        payload.update(_data_state_payload(data))
    if result is not None:
        payload.update(_result_state_payload(result))
    return payload


def update_pipeline_request(_state: Mapping[str, Any], **changes: Any) -> PipelineState:
    return cast(PipelineState, _validated_request_changes(changes))


def update_pipeline_data(_state: Mapping[str, Any], **changes: Any) -> PipelineState:
    return cast(PipelineState, _validated_data_changes(changes))


def update_pipeline_result(_state: Mapping[str, Any], **changes: Any) -> PipelineState:
    return cast(PipelineState, _validated_result_changes(changes))


def merge_state_updates(*updates: Mapping[str, Any]) -> PipelineState:
    payload: PipelineState = {}
    for update in updates:
        payload.update(update)
    return payload


def require_dataset_meta(state: Mapping[str, Any]) -> DatasetMeta:
    dataset_meta = _dataset_meta_value(state.get("dataset_meta"))
    if dataset_meta is None:
        raise ValueError(PIPELINE_DATASET_META_REQUIRED_ERROR)
    return dataset_meta


def _optional_text(field_name: str, value: Any) -> str | None:
    if value in EMPTY_TEXT_VALUES:
        return None
    if not isinstance(value, str):
        raise TypeError(PIPELINE_REQUEST_TEXT_TYPE_ERROR.format(field_name=field_name))
    return value


def _bool_value(field_name: str, value: Any, *, default: bool = False) -> bool:
    if value in EMPTY_TEXT_VALUES:
        return default
    if not isinstance(value, bool):
        raise TypeError(PIPELINE_REQUEST_BOOL_TYPE_ERROR.format(field_name=field_name))
    return value


def _string_list(field_name: str, value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise TypeError(PIPELINE_STRING_LIST_TYPE_ERROR.format(field_name=field_name))
    if all(isinstance(item, str) for item in value):
        return value
    raise TypeError(PIPELINE_STRING_LIST_ITEM_TYPE_ERROR.format(field_name=field_name))


def _row_list(field_name: str, value: Any) -> list[dict[str, str]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise TypeError(PIPELINE_ROW_LIST_TYPE_ERROR.format(field_name=field_name))
    if _is_string_row_list(value):
        return value

    rows: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            raise TypeError(PIPELINE_ROW_LIST_ITEM_TYPE_ERROR.format(field_name=field_name))
        rows.append({str(key): _stringify_cell_value(nested_value) for key, nested_value in item.items()})
    return rows


def _dict_list(field_name: str, value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise TypeError(PIPELINE_DICT_LIST_TYPE_ERROR.format(field_name=field_name))
    if not all(isinstance(item, dict) for item in value):
        raise TypeError(PIPELINE_DICT_LIST_ITEM_TYPE_ERROR.format(field_name=field_name))
    return value


def _dict_value(field_name: str, value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise TypeError(PIPELINE_DICT_TYPE_ERROR.format(field_name=field_name))
    return value


def _column_list(value: Any) -> list[ColumnProfile]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise TypeError(PIPELINE_COLUMNS_TYPE_ERROR)
    if not all(isinstance(item, ColumnProfile) for item in value):
        raise TypeError(PIPELINE_COLUMNS_ITEM_TYPE_ERROR)
    return value


def _finding_list(value: Any) -> list[ValidationFinding]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise TypeError(PIPELINE_FINDINGS_TYPE_ERROR)
    if not all(isinstance(item, ValidationFinding) for item in value):
        raise TypeError(PIPELINE_FINDINGS_ITEM_TYPE_ERROR)
    return value


def _trace_list(value: Any) -> list[AgentTrace]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise TypeError(PIPELINE_AGENT_TRACES_TYPE_ERROR)
    if not all(isinstance(item, AgentTrace) for item in value):
        raise TypeError(PIPELINE_AGENT_TRACES_ITEM_TYPE_ERROR)
    return value


def _validated_request_changes(changes: Mapping[str, Any]) -> PipelineRequestState:
    return cast(
        PipelineRequestState,
        _validated_state_changes(
            "request",
            changes,
            {
                "meta_csv_path": lambda value: _optional_text("meta_csv_path", value),
                "uploaded_dataset_path": lambda value: _optional_text("uploaded_dataset_path", value),
                "uploaded_dataset_name": lambda value: _optional_text("uploaded_dataset_name", value),
                "use_llm_agents": lambda value: _bool_value("use_llm_agents", value),
                "llm_model": lambda value: _optional_text("llm_model", value),
                "llm_fast_model": lambda value: _optional_text("llm_fast_model", value),
                "llm_strong_model": lambda value: _optional_text("llm_strong_model", value),
                "dataset_id": lambda value: _optional_text("dataset_id", value),
                "dataset_name": lambda value: _optional_text("dataset_name", value),
            },
        ),
    )


def _validated_data_changes(changes: Mapping[str, Any]) -> PipelineDataState:
    return cast(
        PipelineDataState,
        _validated_state_changes(
            "data",
            changes,
            {
                "dataset_meta": _dataset_meta_value,
                "preview_headers": lambda value: _string_list("preview_headers", value),
                "preview_rows": lambda value: _row_list("preview_rows", value),
                "validation_rows": lambda value: _row_list("validation_rows", value),
                "relationship_candidates": lambda value: _dict_list("relationship_candidates", value),
                "columns": _column_list,
            },
        ),
    )


def _validated_result_changes(changes: Mapping[str, Any]) -> PipelineResultState:
    return cast(
        PipelineResultState,
        _validated_state_changes(
            "result",
            changes,
            {
                "findings": _finding_list,
                "agent_traces": _trace_list,
                "summary": lambda value: _dict_value("summary", value),
            },
        ),
    )


def _validated_state_changes(
    section: str,
    changes: Mapping[str, Any],
    validators: Mapping[str, Callable[[Any], Any]],
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for field_name, value in changes.items():
        validator = validators.get(field_name)
        if validator is None:
            raise KeyError(PIPELINE_UNKNOWN_FIELD_ERROR.format(section=section, field_name=field_name))
        payload[field_name] = validator(value)
    return payload
