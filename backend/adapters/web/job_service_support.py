from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable
from urllib.parse import quote
from uuid import uuid4

from backend.application.dto import AnalysisJob, AnalysisJobItem, ArtifactRef, PreparedDataset, job_timestamp
from backend.config.reporting import REPORTS_DIR_NAME, RESULTS_DIR_NAME
from backend.infrastructure.io.loaders.loading import iter_uploaded_rows


def build_job_items(
    *,
    job_id: str,
    prepared_datasets: list[PreparedDataset],
    artifact_store,
    repository,
    now: str,
) -> list[AnalysisJobItem]:
    items: list[AnalysisJobItem] = []
    for index, dataset in enumerate(prepared_datasets, start=1):
        item = AnalysisJobItem(
            item_id=uuid4().hex,
            job_id=job_id,
            index=index,
            display_name=dataset.display_name,
            source_type=dataset.source_type,
            response_type=dataset.response_type,
            source_artifact=artifact_store.put_file(
                dataset.path,
                key=f"jobs/{job_id}/inputs/{index:04d}/{dataset.display_name}",
                filename=dataset.display_name,
            ),
            created_at=now,
            updated_at=now,
        )
        repository.save_job_item(item)
        items.append(item)
    return items


def persist_item_result(
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
        persisted_summary["validation_result_download_path"] = artifact_download_path(validation_result_artifact.key)
    if error_report_artifact is not None:
        persisted_summary["error_report_xlsx"] = error_report_artifact.key
        persisted_summary["error_report_download_path"] = artifact_download_path(error_report_artifact.key)

    persisted_response = {**response, "summary": persisted_summary}
    result_artifact = artifact_store.put_json(
        persisted_response,
        key=f"jobs/{job_id}/items/{item.item_id}/result.json",
        filename=f"{Path(item.display_name).stem}_result.json",
    )
    now = job_timestamp()
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
            "completed_at": now,
            "updated_at": now,
        }
    )
    return persisted_response, completed_item


def build_items_payload(
    items: list[AnalysisJobItem],
    *,
    artifact_store,
    success_item: Callable[[str, dict[str, Any]], dict[str, Any]],
    error_item: Callable[[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for item in items:
        if item.status == "completed" and item.result_artifact is not None:
            payload.append(success_item(item.display_name, artifact_store.read_json(item.result_artifact.key)))
            continue
        payload.append(error_item(item.display_name, item.error_message or "분석 실패"))
    return payload


def persist_batch_report(
    *,
    dependencies,
    job_id: str,
    payload: dict[str, Any],
    items: list[dict[str, Any]],
    job_items: list[AnalysisJobItem],
    artifact_store,
) -> ArtifactRef | None:
    if not payload.get("batch"):
        return None

    successful_items = [item for item in items if item.get("ok") and isinstance(item.get("result"), dict)]
    if not successful_items:
        return None

    from .request_utils import _runtime_tmp_dir

    with TemporaryDirectory(prefix=f"analysis_job_batch_{job_id}_", dir=_runtime_tmp_dir()) as tmp_dir:
        output_dir = dependencies.validation_output_dir(Path(tmp_dir) / "batch")
        report_path = dependencies.write_batch_error_report(items=successful_items, output_dir=output_dir)
        batch_report_artifact = artifact_store.put_file(
            report_path,
            key=f"jobs/{job_id}/results/{report_path.name}",
            filename=report_path.name,
        )
        payload["summary"]["error_report_xlsx"] = batch_report_artifact.key
        payload["summary"]["error_report_download_path"] = artifact_download_path(batch_report_artifact.key)
        column_report_entries = _job_batch_column_report_entries(
            items=items,
            job_items=job_items,
            artifact_store=artifact_store,
            tmp_dir=Path(tmp_dir),
        )
        if column_report_entries:
            column_report_paths = _report_paths(
                dependencies.write_batch_column_error_report(
                    entries=column_report_entries,
                    output_dir=output_dir,
                )
            )
            column_report_artifacts = [
                artifact_store.put_file(
                    column_report_path,
                    key=f"jobs/{job_id}/results/{column_report_path.name}",
                    filename=column_report_path.name,
                )
                for column_report_path in column_report_paths
            ]
            if not column_report_artifacts:
                return batch_report_artifact
            first_column_report_artifact = column_report_artifacts[0]
            payload["summary"]["column_error_report_xlsx"] = first_column_report_artifact.key
            payload["summary"]["column_error_report_download_path"] = artifact_download_path(
                first_column_report_artifact.key
            )
            payload["summary"]["column_error_report_xlsx_files"] = [
                artifact.key for artifact in column_report_artifacts
            ]
            payload["summary"]["column_error_report_download_paths"] = [
                artifact_download_path(artifact.key) for artifact in column_report_artifacts
            ]
        return batch_report_artifact


def _report_paths(value: Path | str | list[Path | str]) -> list[Path]:
    if isinstance(value, list):
        return [Path(path) for path in value]
    return [Path(value)]


def refresh_running_job(*, dependencies, job_id: str) -> None:
    repository = job_repository(dependencies)
    refreshed = repository.get_job(job_id)
    if refreshed is None:
        return
    aggregated = aggregate_job(refreshed)
    if aggregated.processed_items < aggregated.total_items:
        aggregated = aggregated.model_copy(
            update={
                "status": "running",
                "started_at": refreshed.started_at or job_timestamp(),
                "updated_at": job_timestamp(),
            }
        )
    repository.save_job(aggregated)


def aggregate_job(job: AnalysisJob) -> AnalysisJob:
    items = list(job.items)
    success_count = sum(1 for item in items if item.status == "completed")
    failed_count = sum(1 for item in items if item.status == "failed")
    error_message = next((item.error_message for item in items if item.status == "failed" and item.error_message), None)
    return job.model_copy(
        update={
            "processed_items": success_count + failed_count,
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


def artifact_download_path(key: str) -> str:
    return f"/api/jobs/artifacts/download?key={quote(key, safe='')}"


def _job_batch_column_report_entries(
    *,
    items: list[dict[str, Any]],
    job_items: list[AnalysisJobItem],
    artifact_store,
    tmp_dir: Path,
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    source_dir = tmp_dir / "column_report_inputs"
    for item, job_item in zip(items, job_items):
        result = item.get("result")
        if not item.get("ok") or not isinstance(result, dict) or job_item.source_artifact is None:
            continue
        normalized_result = result
        if not result.get("summary", {}).get("dataset_name"):
            normalized_result = {
                **result,
                "summary": {
                    **result.get("summary", {}),
                    "dataset_name": job_item.display_name,
                },
            }
        materialized_path = artifact_store.materialize(
            job_item.source_artifact.key,
            target_dir=source_dir / f"{job_item.index:04d}",
            filename=job_item.display_name,
        )
        entries.append(
            {
                "result": normalized_result,
                "validation_rows": list(iter_uploaded_rows(materialized_path)),
            }
        )
    return entries


def job_repository(dependencies):
    if dependencies.analysis_job_repository is None:  # pragma: no cover
        raise RuntimeError("analysis_job_repository dependency가 구성되지 않았습니다.")
    return dependencies.analysis_job_repository()


def artifact_store(dependencies):
    if dependencies.artifact_store is None:  # pragma: no cover
        raise RuntimeError("artifact_store dependency가 구성되지 않았습니다.")
    return dependencies.artifact_store()


def analysis_queue(dependencies):
    if dependencies.analysis_queue is None:  # pragma: no cover
        raise RuntimeError("analysis_queue dependency가 구성되지 않았습니다.")
    return dependencies.analysis_queue()
