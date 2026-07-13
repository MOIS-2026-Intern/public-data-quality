from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from urllib.parse import quote
from uuid import uuid4

from backend.application.dto import (
    AnalysisJob,
    AnalysisJobItem,
    ArtifactDownload,
    ArtifactRef,
    PipelineExecutionRequest,
    PreparedDataset,
    job_timestamp,
)
from backend.config.reporting import REPORTS_DIR_NAME, RESULTS_DIR_NAME

from .analysis_execution import _analysis_error_message, _error_item, _success_item
from .analysis_support import _analysis_payload, _batch_summary
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

        items: list[AnalysisJobItem] = []
        for index, dataset in enumerate(prepared_datasets, start=1):
            item_id = uuid4().hex
            source_artifact = artifact_store.put_file(
                dataset.path,
                key=f"jobs/{job_id}/inputs/{index:04d}/{dataset.display_name}",
                filename=dataset.display_name,
            )
            item = AnalysisJobItem(
                item_id=item_id,
                job_id=job_id,
                index=index,
                display_name=dataset.display_name,
                source_type=dataset.source_type,
                response_type=dataset.response_type,
                source_artifact=source_artifact,
                created_at=now,
                updated_at=now,
            )
            repository.save_job_item(item)
            items.append(item)

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
                persisted_response, completed_item = self._persist_item_result(
                    job_id=job_id,
                    item=running_item,
                    response=response,
                    artifact_store=artifact_store,
                    output_dir=output_dir,
                )
                repository.save_job_item(completed_item)
                self._refresh_running_job(job_id=job_id)
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
                self._refresh_running_job(job_id=job_id)
                return {"ok": False, "filename": running_item.display_name, "error": error_message}

    def finalize_job(self, *, job_id: str, item_results: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        repository = _job_repository(self.dependencies)
        artifact_store = _artifact_store(self.dependencies)
        job = repository.get_job(job_id)
        if job is None:
            raise ValueError(f"analysis job를 찾을 수 없습니다: {job_id}")

        items_payload = self._build_items_payload(job.items, artifact_store=artifact_store)
        payload = _analysis_payload(items_payload, summary=_batch_summary(items_payload))
        batch_report_artifact = self._persist_batch_report(
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

    def _persist_item_result(
        self,
        *,
        job_id: str,
        item: AnalysisJobItem,
        response: dict[str, Any],
        artifact_store,
        output_dir: Path,
    ) -> tuple[dict[str, Any], AnalysisJobItem]:
        summary = response.get("summary") or {}
        dataset_name = str(summary.get("dataset_name") or item.display_name)
        validation_result_name = str(summary.get("validation_result_csv") or "")
        error_report_name = str(summary.get("error_report_xlsx") or "")
        validation_result_artifact = None
        error_report_artifact = None

        if validation_result_name:
            validation_result_artifact = artifact_store.put_file(
                output_dir / RESULTS_DIR_NAME / validation_result_name,
                key=f"jobs/{job_id}/items/{item.item_id}/artifacts/{validation_result_name}",
                filename=validation_result_name,
            )
        if error_report_name:
            error_report_artifact = artifact_store.put_file(
                output_dir / REPORTS_DIR_NAME / error_report_name,
                key=f"jobs/{job_id}/items/{item.item_id}/artifacts/{error_report_name}",
                filename=error_report_name,
            )

        persisted_summary = dict(summary)
        if validation_result_artifact is not None:
            persisted_summary["validation_result_csv"] = validation_result_artifact.key
            persisted_summary["validation_result_download_path"] = _artifact_download_path(validation_result_artifact.key)
        if error_report_artifact is not None:
            persisted_summary["error_report_xlsx"] = error_report_artifact.key
            persisted_summary["error_report_download_path"] = _artifact_download_path(error_report_artifact.key)

        persisted_response = {**response, "summary": persisted_summary}
        result_artifact = artifact_store.put_json(
            persisted_response,
            key=f"jobs/{job_id}/items/{item.item_id}/result.json",
            filename=f"{Path(item.display_name).stem}_result.json",
        )

        completed_item = item.model_copy(
            update={
                "status": "completed",
                "dataset_name": dataset_name,
                "result_artifact": result_artifact,
                "validation_result_artifact": validation_result_artifact,
                "error_report_artifact": error_report_artifact,
                "row_count": int(persisted_summary.get("row_count") or 0),
                "column_count": int(persisted_summary.get("column_count") or 0),
                "finding_count": int(persisted_summary.get("finding_count") or 0),
                "issue_finding_count": int(persisted_summary.get("issue_finding_count") or 0),
                "manual_review_finding_count": int(persisted_summary.get("manual_review_finding_count") or 0),
                "error_message": None,
                "completed_at": job_timestamp(),
                "updated_at": job_timestamp(),
            }
        )
        return persisted_response, completed_item

    def _build_items_payload(self, items: list[AnalysisJobItem], *, artifact_store) -> list[dict[str, Any]]:
        payload: list[dict[str, Any]] = []
        for item in items:
            if item.status == "completed" and item.result_artifact is not None:
                payload.append(
                    _success_item(
                        item.display_name,
                        artifact_store.read_json(item.result_artifact.key),
                    )
                )
                continue
            payload.append(_error_item(item.display_name, item.error_message or "분석 실패"))
        return payload

    def _persist_batch_report(
        self,
        *,
        job_id: str,
        payload: dict[str, Any],
        items: list[dict[str, Any]],
        artifact_store,
    ) -> ArtifactRef | None:
        if not payload.get("batch"):
            return None

        successful_items = [item for item in items if item.get("ok") and isinstance(item.get("result"), dict)]
        if not successful_items:
            return None

        with TemporaryDirectory(prefix=f"analysis_job_batch_{job_id}_", dir=_runtime_tmp_dir()) as tmp_dir:
            output_dir = self.dependencies.validation_output_dir(Path(tmp_dir) / "batch")
            report_path = self.dependencies.write_batch_error_report(
                items=successful_items,
                output_dir=output_dir,
            )
            batch_report_artifact = artifact_store.put_file(
                report_path,
                key=f"jobs/{job_id}/results/{report_path.name}",
                filename=report_path.name,
            )
            payload["summary"]["error_report_xlsx"] = batch_report_artifact.key
            payload["summary"]["error_report_download_path"] = _artifact_download_path(batch_report_artifact.key)
            return batch_report_artifact

    def _refresh_running_job(self, *, job_id: str) -> None:
        repository = _job_repository(self.dependencies)
        refreshed = repository.get_job(job_id)
        if refreshed is None:
            return
        aggregated = _aggregate_job(refreshed)
        if aggregated.processed_items < aggregated.total_items:
            aggregated = aggregated.model_copy(
                update={
                    "status": "running",
                    "started_at": refreshed.started_at or job_timestamp(),
                    "updated_at": job_timestamp(),
                }
            )
        repository.save_job(aggregated)


def async_analysis_job_service(
    *,
    dependencies: WebAdapterDependencies | None = None,
) -> AsyncAnalysisJobService:
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


def get_analysis_job(
    job_id: str,
    *,
    dependencies: WebAdapterDependencies | None = None,
) -> AnalysisJob | None:
    return async_analysis_job_service(dependencies=dependencies).get_job(job_id)


def get_analysis_job_result(
    job_id: str,
    *,
    dependencies: WebAdapterDependencies | None = None,
) -> tuple[dict[str, Any] | None, AnalysisJob | None]:
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


def resolve_analysis_artifact_download(
    key: str,
    *,
    dependencies: WebAdapterDependencies | None = None,
) -> ArtifactDownload:
    return async_analysis_job_service(dependencies=dependencies).resolve_artifact_download(key)


def _aggregate_job(job: AnalysisJob) -> AnalysisJob:
    items = list(job.items)
    success_count = sum(1 for item in items if item.status == "completed")
    failed_count = sum(1 for item in items if item.status == "failed")
    processed_items = success_count + failed_count
    error_message = next((item.error_message for item in items if item.status == "failed" and item.error_message), None)
    return job.model_copy(
        update={
            "processed_items": processed_items,
            "success_count": success_count,
            "failed_count": failed_count,
            "row_count": sum(item.row_count for item in items),
            "finding_count": sum(item.finding_count for item in items),
            "issue_finding_count": sum(item.issue_finding_count for item in items),
            "manual_review_finding_count": sum(item.manual_review_finding_count for item in items),
            "error_message": error_message,
            "items": items,
            "updated_at": job_timestamp(),
        }
    )


def _artifact_download_path(key: str) -> str:
    return f"/api/jobs/artifacts/download?key={quote(key, safe='')}"


def _job_repository(dependencies: WebAdapterDependencies):
    if dependencies.analysis_job_repository is None:  # pragma: no cover
        raise RuntimeError("analysis_job_repository dependency가 구성되지 않았습니다.")
    return dependencies.analysis_job_repository()


def _artifact_store(dependencies: WebAdapterDependencies):
    if dependencies.artifact_store is None:  # pragma: no cover
        raise RuntimeError("artifact_store dependency가 구성되지 않았습니다.")
    return dependencies.artifact_store()


def _analysis_queue(dependencies: WebAdapterDependencies):
    if dependencies.analysis_queue is None:  # pragma: no cover
        raise RuntimeError("analysis_queue dependency가 구성되지 않았습니다.")
    return dependencies.analysis_queue()
