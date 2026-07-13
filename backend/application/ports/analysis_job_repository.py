from __future__ import annotations

from typing import Protocol

from backend.application.dto import AnalysisJob, AnalysisJobItem


class AnalysisJobRepositoryPort(Protocol):
    def save_job(self, job: AnalysisJob) -> AnalysisJob: ...

    def save_job_item(self, item: AnalysisJobItem) -> AnalysisJobItem: ...

    def get_job(self, job_id: str, *, with_items: bool = True) -> AnalysisJob | None: ...

    def get_job_item(self, item_id: str) -> AnalysisJobItem | None: ...

    def list_job_items(self, job_id: str) -> list[AnalysisJobItem]: ...

