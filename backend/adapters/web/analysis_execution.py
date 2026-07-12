from __future__ import annotations

from collections.abc import Callable, Iterator

from backend.application.dto import PipelineExecutionRequest, PreparedDataset
from backend.config.pipeline import PIPELINE_PROGRESS_STEPS, REPORT_PROGRESS_STEP

from .error_support import (
    UNEXPECTED_ANALYSIS_ERROR_MESSAGE,
    log_unexpected_exception,
    public_exception_message,
)
from .analysis_support import (
    AnalysisItem,
    AnalysisPayload,
    _analyze_prepared_dataset,
    _analysis_payload,
    _analysis_result_payload,
    _batch_summary,
    _progress_event,
    _stage_steps,
)
from .dependencies import WebAdapterDependencies, default_web_dependencies
from .pipeline_service import stream_pipeline

AnalysisOptions = PipelineExecutionRequest

__all__ = [
    "analyze_prepared_datasets",
    "analyze_batch_prepared_datasets",
    "stream_analysis_events",
]


def _resolve_dependencies(dependencies: WebAdapterDependencies | None) -> WebAdapterDependencies:
    return dependencies or default_web_dependencies()


def analyze_prepared_datasets(
    *,
    prepared_datasets: list[PreparedDataset],
    options: AnalysisOptions,
    dependencies: WebAdapterDependencies | None = None,
) -> tuple[AnalysisPayload, int]:
    resolved_dependencies = _resolve_dependencies(dependencies)
    items = [
        _analyze_dataset_item(
            dataset=dataset,
            options=options,
            dependencies=resolved_dependencies,
        )
        for dataset in prepared_datasets
    ]
    summary = _batch_summary(items)
    status_code = 200 if summary["success_count"] else 400
    return _analysis_payload(items, summary=summary), status_code


def analyze_batch_prepared_datasets(
    *,
    prepared_datasets: list[PreparedDataset],
    options: AnalysisOptions,
    dependencies: WebAdapterDependencies | None = None,
) -> tuple[AnalysisPayload, int]:
    return analyze_prepared_datasets(
        prepared_datasets=prepared_datasets,
        options=options,
        dependencies=dependencies,
    )


def stream_analysis_events(
    *,
    prepared_datasets: list[PreparedDataset],
    options: AnalysisOptions,
    dependencies: WebAdapterDependencies | None = None,
    cleanup: Callable[[], None],
) -> Iterator[bytes]:
    resolved_dependencies = _resolve_dependencies(dependencies)
    total_files = len(prepared_datasets)
    items: list[AnalysisItem] = []
    final_stage_index = len(PIPELINE_PROGRESS_STEPS) + 1
    try:
        yield _progress_event(
            "progress",
            progress=0,
            current=0,
            total=total_files,
            message="분석 준비 중",
            stage_index=0,
            stage_total=final_stage_index,
            stages=_stage_steps(0),
        )

        for index, dataset in enumerate(prepared_datasets, start=1):
            yield _dataset_started_event(index=index, total_files=total_files, dataset=dataset)
            try:
                result = yield from _stream_dataset_events(
                    index=index,
                    total_files=total_files,
                    dataset=dataset,
                    options=options,
                    dependencies=resolved_dependencies,
                )
                items.append(_success_item(dataset.display_name, result))
                yield _dataset_finished_event(
                    event_type="file_done",
                    index=index,
                    total_files=total_files,
                    filename=dataset.display_name,
                    message="완료",
                    final_stage_index=final_stage_index,
                )
            except Exception as exc:  # pragma: no cover
                error_message = _analysis_error_message(exc)
                items.append(_error_item(dataset.display_name, error_message))
                yield _dataset_finished_event(
                    event_type="file_error",
                    index=index,
                    total_files=total_files,
                    filename=dataset.display_name,
                    message="실패",
                    final_stage_index=final_stage_index,
                    error=error_message,
                )

        yield _progress_event(
            "final",
            progress=100,
            current=total_files,
            total=total_files,
            message="분석 완료",
            payload=_final_payload(items),
        )
    finally:
        cleanup()


def _analyze_dataset_item(
    *,
    dataset: PreparedDataset,
    options: AnalysisOptions,
    dependencies: WebAdapterDependencies,
) -> AnalysisItem:
    try:
        result = _analyze_prepared_dataset(
            dataset=dataset,
            request=options,
            dependencies=dependencies,
        )
        return _success_item(dataset.display_name, result)
    except Exception as exc:  # pragma: no cover
        return _error_item(dataset.display_name, _analysis_error_message(exc))


def _stream_dataset_events(
    *,
    index: int,
    total_files: int,
    dataset: PreparedDataset,
    options: AnalysisOptions,
    dependencies: WebAdapterDependencies,
) -> Iterator[bytes]:
    result = None
    for pipeline_event in stream_pipeline(
        request=options.model_copy(
            update={
                "uploaded_dataset_csv": str(dataset.path),
                "uploaded_dataset_name": dataset.display_name,
            }
        ),
        dependencies=dependencies,
    ):
        if pipeline_event.get("kind") == "result":
            payload = pipeline_event.get("result")
            if payload is not None:
                result = _analysis_result_payload(payload, dependencies=dependencies)
            continue
        progress_payload = _pipeline_progress_payload(
            index=index,
            total_files=total_files,
            filename=dataset.display_name,
            pipeline_event=pipeline_event,
        )
        if progress_payload is not None:
            yield progress_payload

    if result is None:
        raise RuntimeError("분석 결과를 생성하지 못했습니다.")
    return result


def _pipeline_progress_payload(
    *,
    index: int,
    total_files: int,
    filename: str,
    pipeline_event: dict[str, Any],
) -> bytes | None:
    if pipeline_event.get("kind") != "progress":
        return None

    stage_index = int(pipeline_event.get("stage_index") or 0)
    stage_total = int(pipeline_event.get("stage_total") or 1)
    completed_stage_index = _completed_stage_index(pipeline_event, stage_index)
    stage_fraction = stage_index / max(1, stage_total)
    progress = int(((index - 1 + stage_fraction) / total_files) * 100)
    return _progress_event(
        "progress",
        progress=min(progress, 99),
        current=index - 1,
        total=total_files,
        filename=filename,
        stage_label=pipeline_event.get("stage_label", ""),
        stage_index=stage_index,
        stage_total=stage_total,
        stages=_stage_steps(completed_stage_index),
        message=pipeline_event.get("message", "분석 중"),
    )


def _completed_stage_index(pipeline_event: dict[str, Any], stage_index: int) -> int:
    if pipeline_event.get("node") == REPORT_PROGRESS_STEP[0]:
        return stage_index - 1
    return stage_index


def _dataset_started_event(
    *,
    index: int,
    total_files: int,
    dataset: PreparedDataset,
) -> bytes:
    started_progress = int(((index - 1) / total_files) * 100)
    return _progress_event(
        "progress",
        progress=started_progress,
        current=index - 1,
        total=total_files,
        filename=dataset.display_name,
        message="분석 중",
        stage_index=0,
        stage_total=len(PIPELINE_PROGRESS_STEPS) + 1,
        stages=_stage_steps(0),
    )


def _dataset_finished_event(
    *,
    event_type: str,
    index: int,
    total_files: int,
    filename: str,
    message: str,
    final_stage_index: int,
    error: str | None = None,
) -> bytes:
    payload: dict[str, Any] = {
        "progress": int((index / total_files) * 100),
        "current": index,
        "total": total_files,
        "filename": filename,
        "stage_index": final_stage_index,
        "stage_total": final_stage_index,
        "stages": _stage_steps(final_stage_index),
        "message": message,
    }
    if error:
        payload["error"] = error
    return _progress_event(event_type, **payload)


def _final_payload(items: list[AnalysisItem]) -> AnalysisPayload:
    return _analysis_payload(items)


def _success_item(filename: str, result: dict[str, Any]) -> AnalysisItem:
    return {"ok": True, "filename": filename, "result": result}


def _analysis_error_message(exc: Exception) -> str:
    error_message = public_exception_message(
        exc,
        unexpected_message=UNEXPECTED_ANALYSIS_ERROR_MESSAGE,
    )
    if error_message == UNEXPECTED_ANALYSIS_ERROR_MESSAGE:
        log_unexpected_exception("Dataset analysis failed unexpectedly")
    return error_message


def _error_item(filename: str, error_message: str) -> AnalysisItem:
    return {
        "ok": False,
        "filename": filename,
        "error": error_message,
    }
