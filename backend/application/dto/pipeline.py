from __future__ import annotations

from typing import Any, TypedDict

from pydantic import BaseModel

from backend.domain.entities.models import ColumnProfile, DatasetMeta, ValidationFinding


class AgentTrace(BaseModel):
    agent_name: str
    action: str
    target: str | None = None
    detail: str = ""


class PipelineState(TypedDict, total=False):
    meta_csv_path: str
    uploaded_dataset_path: str
    uploaded_dataset_name: str
    use_llm_agents: bool
    llm_model: str | None
    llm_fast_model: str | None
    llm_strong_model: str | None
    dataset_id: str
    dataset_name: str
    dataset_meta: DatasetMeta
    preview_headers: list[str]
    preview_rows: list[dict[str, str]]
    validation_rows: list[dict[str, str]]
    relationship_candidates: list[dict[str, Any]]
    columns: list[ColumnProfile]
    findings: list[ValidationFinding]
    agent_traces: list[AgentTrace]
    summary: dict[str, Any]
