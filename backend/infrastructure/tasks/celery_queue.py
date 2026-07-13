from __future__ import annotations

from backend.application.ports import AnalysisJobRepositoryPort


class CeleryAnalysisQueue:
    def __init__(self, job_repository: AnalysisJobRepositoryPort):
        self.job_repository = job_repository

    def enqueue_job(self, job_id: str) -> str | None:
        from celery import chord

        from .tasks import finalize_analysis_job_task, process_analysis_job_item_task

        items = self.job_repository.list_job_items(job_id)
        if not items:
            result = finalize_analysis_job_task.delay([], job_id)
            return result.id

        item_tasks = [process_analysis_job_item_task.s(job_id, item.item_id) for item in items]
        result = chord(item_tasks)(finalize_analysis_job_task.s(job_id))
        return result.id
