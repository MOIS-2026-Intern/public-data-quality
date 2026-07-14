from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

from pydantic import BaseModel, Field

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
