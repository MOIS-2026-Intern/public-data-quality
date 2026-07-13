from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from .pipeline import PipelineExecutionRequest

AnalysisJobStatus = Literal["queued", "running", "completed", "partial_failed", "failed"]
AnalysisJobItemStatus = Literal["queued", "running", "completed", "failed"]


def job_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class ArtifactRef(BaseModel):
    key: str
    filename: str
    content_type: str = "application/octet-stream"
    size_bytes: int = 0


class ArtifactDownload(BaseModel):
    key: str
    path: Path
    filename: str
    content_type: str = "application/octet-stream"


class AnalysisJobItem(BaseModel):
    item_id: str
    job_id: str
    index: int
    display_name: str
    source_type: str
    response_type: str | None = None
    status: AnalysisJobItemStatus = "queued"
    dataset_name: str | None = None
    source_artifact: ArtifactRef | None = None
    result_artifact: ArtifactRef | None = None
    validation_result_artifact: ArtifactRef | None = None
    error_report_artifact: ArtifactRef | None = None
    error_message: str | None = None
    row_count: int = 0
    column_count: int = 0
    finding_count: int = 0
    issue_finding_count: int = 0
    manual_review_finding_count: int = 0
    created_at: str = Field(default_factory=job_timestamp)
    updated_at: str = Field(default_factory=job_timestamp)
    started_at: str | None = None
    completed_at: str | None = None


class AnalysisJob(BaseModel):
    job_id: str
    status: AnalysisJobStatus = "queued"
    queue_backend: str = "celery"
    queue_task_id: str | None = None
    request: PipelineExecutionRequest = Field(default_factory=PipelineExecutionRequest)
    total_items: int = 0
    processed_items: int = 0
    success_count: int = 0
    failed_count: int = 0
    row_count: int = 0
    finding_count: int = 0
    issue_finding_count: int = 0
    manual_review_finding_count: int = 0
    batch_result_artifact: ArtifactRef | None = None
    batch_report_artifact: ArtifactRef | None = None
    error_message: str | None = None
    created_at: str = Field(default_factory=job_timestamp)
    updated_at: str = Field(default_factory=job_timestamp)
    started_at: str | None = None
    completed_at: str | None = None
    items: list[AnalysisJobItem] = Field(default_factory=list)

    def public_payload(self) -> dict[str, Any]:
        payload = self.model_dump(mode="json")
        request = payload.get("request") or {}
        if isinstance(request, dict):
            request.pop("openai_api_key", None)
        for item in payload.get("items") or []:
            if isinstance(item, dict):
                item.pop("source_artifact", None)
        return payload

