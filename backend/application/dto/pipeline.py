from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Callable, TypedDict, cast

from pydantic import BaseModel, Field

from backend.config.common import EMPTY_TEXT_VALUES
from backend.config.pipeline import (
    PIPELINE_AGENT_TRACES_ITEM_TYPE_ERROR,
    PIPELINE_AGENT_TRACES_TYPE_ERROR,
    PIPELINE_COLUMNS_ITEM_TYPE_ERROR,
    PIPELINE_COLUMNS_TYPE_ERROR,
    PIPELINE_DATASET_META_REQUIRED_ERROR,
    PIPELINE_DATASET_META_TYPE_ERROR,
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


class AgentTrace(BaseModel):
    agent_name: str
    action: str
    target: str | None = None
    detail: str = ""


class PipelineRequest(BaseModel):
    meta_csv_path: str | None = None
    uploaded_dataset_path: str | None = None
    uploaded_dataset_name: str | None = None
    use_llm_agents: bool = False
    llm_model: str | None = None
    llm_fast_model: str | None = None
    llm_strong_model: str | None = None
    dataset_id: str | None = None
    dataset_name: str | None = None


class PipelineExecutionRequest(BaseModel):
    dataset_id: str | None = None
    dataset_name: str | None = None
    meta_csv: str | None = None
    uploaded_dataset_csv: str | None = None
    uploaded_dataset_name: str | None = None
    use_llm_agents: bool = False
    openai_api_key: str | None = None
    llm_model: str | None = None
    llm_fast_model: str | None = None
    llm_strong_model: str | None = None

    def to_pipeline_request(self) -> PipelineRequest:
        return PipelineRequest(
            dataset_id=self.dataset_id,
            dataset_name=self.dataset_name,
            meta_csv_path=str(Path(self.meta_csv)) if self.meta_csv else None,
            uploaded_dataset_path=str(Path(self.uploaded_dataset_csv)) if self.uploaded_dataset_csv else None,
            uploaded_dataset_name=self.uploaded_dataset_name,
            use_llm_agents=self.use_llm_agents,
            llm_model=self.llm_model,
            llm_fast_model=self.llm_fast_model,
            llm_strong_model=self.llm_strong_model,
        )


class PipelineData(BaseModel):
    dataset_meta: DatasetMeta | None = None
    preview_headers: list[str] = Field(default_factory=list)
    preview_rows: list[dict[str, str]] = Field(default_factory=list)
    validation_rows: list[dict[str, str]] = Field(default_factory=list)
    relationship_candidates: list[dict[str, Any]] = Field(default_factory=list)
    columns: list[ColumnProfile] = Field(default_factory=list)


class PipelineResult(BaseModel):
    findings: list[ValidationFinding] = Field(default_factory=list)
    agent_traces: list[AgentTrace] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)


class PipelineRequestState(TypedDict, total=False):
    meta_csv_path: str | None
    uploaded_dataset_path: str | None
    uploaded_dataset_name: str | None
    use_llm_agents: bool
    llm_model: str | None
    llm_fast_model: str | None
    llm_strong_model: str | None
    dataset_id: str | None
    dataset_name: str | None


class PipelineDataState(TypedDict, total=False):
    dataset_meta: DatasetMeta
    preview_headers: list[str]
    preview_rows: list[dict[str, str]]
    validation_rows: list[dict[str, str]]
    relationship_candidates: list[dict[str, Any]]
    columns: list[ColumnProfile]


class PipelineResultState(TypedDict, total=False):
    findings: list[ValidationFinding]
    agent_traces: list[AgentTrace]
    summary: dict[str, Any]


class PipelineState(PipelineRequestState, PipelineDataState, PipelineResultState, total=False):
    pass


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
    if validation_rows:
        return validation_rows
    return _row_list("preview_rows", state.get("preview_rows"))


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


def _request_state_payload(request: PipelineRequest) -> PipelineRequestState:
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


def _data_state_payload(data: PipelineData) -> PipelineDataState:
    return {
        "dataset_meta": data.dataset_meta,
        "preview_headers": data.preview_headers,
        "preview_rows": data.preview_rows,
        "validation_rows": data.validation_rows,
        "relationship_candidates": data.relationship_candidates,
        "columns": data.columns,
    }


def _result_state_payload(result: PipelineResult) -> PipelineResultState:
    return {
        "findings": result.findings,
        "agent_traces": result.agent_traces,
        "summary": result.summary,
    }


def _dataset_meta_value(value: Any) -> DatasetMeta | None:
    if value is None:
        return None
    if not isinstance(value, DatasetMeta):
        raise TypeError(PIPELINE_DATASET_META_TYPE_ERROR)
    return value


def _stringify_cell_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _is_string_row_list(value: list[Any]) -> bool:
    for item in value:
        if not isinstance(item, dict):
            return False
        if not all(isinstance(key, str) and isinstance(nested_value, str) for key, nested_value in item.items()):
            return False
    return True


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
