from __future__ import annotations

from .celery_app import celery_app


@celery_app().task(name="analysis.process_job_item")
def process_analysis_job_item_task(job_id: str, item_id: str) -> dict:
    from backend.adapters.web.job_service import process_analysis_job_item

    return process_analysis_job_item(job_id=job_id, item_id=item_id)


@celery_app().task(name="analysis.finalize_job")
def finalize_analysis_job_task(item_results: list[dict], job_id: str) -> dict:
    from backend.adapters.web.job_service import finalize_analysis_job

    return finalize_analysis_job(job_id=job_id, item_results=item_results)

