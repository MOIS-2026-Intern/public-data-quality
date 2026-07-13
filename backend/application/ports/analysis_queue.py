from __future__ import annotations

from typing import Protocol


class AnalysisQueuePort(Protocol):
    def enqueue_job(self, job_id: str) -> str | None: ...

