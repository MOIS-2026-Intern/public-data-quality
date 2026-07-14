from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from uuid import uuid4

from backend.application.dto import (
    AnalysisJob,
    ArtifactDownload,
    PipelineExecutionRequest,
    PreparedDataset,
    job_timestamp,
)

from .analysis_execution import _analysis_error_message, _error_item, _success_item
from .analysis_support import _analysis_payload, _batch_summary
from .job_service_support import (
    aggregate_job as _aggregate_job,
    analysis_queue as _analysis_queue,
    artifact_store as _artifact_store,
    build_items_payload,
    build_job_items,
    job_repository as _job_repository,
    persist_batch_report,
    persist_item_result,
    refresh_running_job,
)
from .dependencies import WebAdapterDependencies, default_web_dependencies
from .pipeline_service import run_pipeline
from .request_utils import _runtime_tmp_dir


def _resolve_dependencies(dependencies: WebAdapterDependencies | None) -> WebAdapterDependencies:
    return dependencies or default_web_dependencies()


@dataclass(frozen=True)
class AsyncAnalysisJobService:
    dependencies: WebAdapterDependencies

    def submit(
        self,
        *,
        prepared_datasets: list[PreparedDataset],
        request: PipelineExecutionRequest,
    ) -> AnalysisJob:
        repository = _job_repository(self.dependencies)
        artifact_store = _artifact_store(self.dependencies)
        queue = _analysis_queue(self.dependencies)
        now = job_timestamp()
        job_id = uuid4().hex

        items = build_job_items(
            job_id=job_id,
            prepared_datasets=prepared_datasets,
            artifact_store=artifact_store,
            repository=repository,
            now=now,
        )

        job = AnalysisJob(
            job_id=job_id,
            status="queued",
            queue_backend=self.dependencies.analysis_queue_backend,
            request=request.model_copy(deep=True),
            total_items=len(items),
            created_at=now,
            updated_at=now,
            items=items,
        )
        repository.save_job(job)
        queue_task_id = queue.enqueue_job(job_id)
        if queue_task_id:
            queued_job = repository.get_job(job_id) or job
            repository.save_job(
                queued_job.model_copy(
                    update={
                        "queue_task_id": queue_task_id,
                        "updated_at": job_timestamp(),
                    }
                )
            )
        stored = repository.get_job(job_id)
        if stored is None:  # pragma: no cover
            raise RuntimeError("analysis job를 생성하지 못했습니다.")
        return stored

    def get_job(self, job_id: str) -> AnalysisJob | None:
        return _job_repository(self.dependencies).get_job(job_id)

    def get_result(self, job_id: str) -> tuple[dict[str, Any] | None, AnalysisJob | None]:
        job = self.get_job(job_id)
        if job is None:
            return None, None
        if job.batch_result_artifact is None:
            return None, job
        return _artifact_store(self.dependencies).read_json(job.batch_result_artifact.key), job

    def process_job_item(self, *, job_id: str, item_id: str) -> dict[str, Any]:
        repository = _job_repository(self.dependencies)
        artifact_store = _artifact_store(self.dependencies)
        job = repository.get_job(job_id, with_items=False)
        item = repository.get_job_item(item_id)
        if job is None or item is None:
            raise ValueError(f"analysis job item을 찾을 수 없습니다: {job_id}/{item_id}")

        if item.status == "completed" and item.result_artifact is not None:
            return {"ok": True, "filename": item.display_name, "result_artifact_key": item.result_artifact.key}
        if item.status == "failed":
            return {"ok": False, "filename": item.display_name, "error": item.error_message or "분석 실패"}

        now = job_timestamp()
        repository.save_job(
            job.model_copy(
                update={
                    "status": "running",
                    "started_at": job.started_at or now,
                    "updated_at": now,
                }
            )
        )
        running_item = item.model_copy(
            update={
                "status": "running",
                "started_at": item.started_at or now,
                "updated_at": now,
            }
        )
        repository.save_job_item(running_item)

        if running_item.source_artifact is None:  # pragma: no cover
            raise ValueError(f"source artifact가 없는 analysis item입니다: {running_item.item_id}")

        with TemporaryDirectory(prefix=f"analysis_job_item_{item_id}_", dir=_runtime_tmp_dir()) as tmp_dir:
            item_dir = Path(tmp_dir)
            input_dir = item_dir / "input"
            output_base_dir = item_dir / "outputs"

            try:
                materialized_path = artifact_store.materialize(
                    running_item.source_artifact.key,
                    target_dir=input_dir,
                    filename=running_item.display_name,
                )
                pipeline_result = run_pipeline(
                    request=job.request.model_copy(
                        update={
                            "uploaded_dataset_csv": str(materialized_path),
                            "uploaded_dataset_name": running_item.display_name,
                        }
                    ),
                    dependencies=self.dependencies,
                )
                output_dir = self.dependencies.validation_output_dir(output_base_dir)
                response = self.dependencies.attach_report_paths(
                    response=pipeline_result.response,
                    validation_rows=pipeline_result.validation_rows,
                    output_dir=output_dir,
                )
                persisted_response, completed_item = persist_item_result(
                    job_id=job_id,
                    item=running_item,
                    response=response,
                    artifact_store=artifact_store,
                    output_dir=output_dir,
                )
                repository.save_job_item(completed_item)
                refresh_running_job(dependencies=self.dependencies, job_id=job_id)
                return {
                    "ok": True,
                    "filename": completed_item.display_name,
                    "result_artifact_key": completed_item.result_artifact.key if completed_item.result_artifact else "",
                    "result": persisted_response,
                }
            except Exception as exc:  # pragma: no cover
                error_message = _analysis_error_message(exc)
                repository.save_job_item(
                    running_item.model_copy(
                        update={
                            "status": "failed",
                            "error_message": error_message,
                            "completed_at": job_timestamp(),
                            "updated_at": job_timestamp(),
                        }
                    )
                )
                refresh_running_job(dependencies=self.dependencies, job_id=job_id)
                return {"ok": False, "filename": running_item.display_name, "error": error_message}

    def finalize_job(self, *, job_id: str, item_results: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        repository = _job_repository(self.dependencies)
        artifact_store = _artifact_store(self.dependencies)
        job = repository.get_job(job_id)
        if job is None:
            raise ValueError(f"analysis job를 찾을 수 없습니다: {job_id}")

        items_payload = build_items_payload(
            job.items,
            artifact_store=artifact_store,
            success_item=_success_item,
            error_item=_error_item,
        )
        payload = _analysis_payload(items_payload, summary=_batch_summary(items_payload))
        batch_report_artifact = persist_batch_report(
            dependencies=self.dependencies,
            job_id=job_id,
            payload=payload,
            items=items_payload,
            artifact_store=artifact_store,
        )
        batch_result_artifact = artifact_store.put_json(
            payload,
            key=f"jobs/{job_id}/results/batch_result.json",
            filename="batch_result.json",
        )

        completed = _aggregate_job(job.model_copy(update={"items": job.items}))
        final_status = (
            "completed"
            if completed.success_count == completed.total_items
            else "failed"
            if completed.success_count == 0
            else "partial_failed"
        )
        repository.save_job(
            completed.model_copy(
                update={
                    "status": final_status,
                    "batch_result_artifact": batch_result_artifact,
                    "batch_report_artifact": batch_report_artifact,
                    "completed_at": job_timestamp(),
                    "updated_at": job_timestamp(),
                }
            )
        )
        return payload

    def resolve_artifact_download(self, key: str) -> ArtifactDownload:
        return _artifact_store(self.dependencies).resolve_download(key)
def async_analysis_job_service(*, dependencies: WebAdapterDependencies | None = None) -> AsyncAnalysisJobService:
    return AsyncAnalysisJobService(dependencies=_resolve_dependencies(dependencies))


def submit_analysis_job(
    *,
    prepared_datasets: list[PreparedDataset],
    request: PipelineExecutionRequest,
    dependencies: WebAdapterDependencies | None = None,
) -> AnalysisJob:
    return async_analysis_job_service(dependencies=dependencies).submit(
        prepared_datasets=prepared_datasets,
        request=request,
    )


def get_analysis_job(job_id: str, *, dependencies: WebAdapterDependencies | None = None) -> AnalysisJob | None:
    return async_analysis_job_service(dependencies=dependencies).get_job(job_id)


def get_analysis_job_result(job_id: str, *, dependencies: WebAdapterDependencies | None = None) -> tuple[dict[str, Any] | None, AnalysisJob | None]:
    return async_analysis_job_service(dependencies=dependencies).get_result(job_id)


def process_analysis_job_item(
    *,
    job_id: str,
    item_id: str,
    dependencies: WebAdapterDependencies | None = None,
) -> dict[str, Any]:
    return async_analysis_job_service(dependencies=dependencies).process_job_item(job_id=job_id, item_id=item_id)


def finalize_analysis_job(
    *,
    job_id: str,
    item_results: list[dict[str, Any]] | None = None,
    dependencies: WebAdapterDependencies | None = None,
) -> dict[str, Any]:
    return async_analysis_job_service(dependencies=dependencies).finalize_job(job_id=job_id, item_results=item_results)


def resolve_analysis_artifact_download(key: str, *, dependencies: WebAdapterDependencies | None = None) -> ArtifactDownload:
    return async_analysis_job_service(dependencies=dependencies).resolve_artifact_download(key)
