from __future__ import annotations

from collections.abc import Callable, Iterator

from backend.application.dto import PipelineExecutionRequest, PreparedDataset
from backend.config.pipeline import PIPELINE_PROGRESS_STEPS
from .analysis_support import (
    AnalysisItem,
    AnalysisPayload,
    _attach_batch_report_path,
    _analyze_prepared_dataset,
    _analysis_payload,
    _analysis_result_payload,
    _batch_summary,
    _progress_event,
    _stage_steps,
)
from .analysis_execution_items import (
    analysis_error_message as _analysis_error_message,
    error_item as _error_item,
    success_item as _success_item,
)
from .analysis_execution_progress import (
    dataset_finished_event as _dataset_finished_event,
    dataset_started_event as _dataset_started_event,
    final_payload as _final_payload,
    pipeline_progress_payload as _pipeline_progress_payload,
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
    return (
        _attach_batch_report_path(
            _analysis_payload(items, summary=summary),
            items=items,
            dependencies=resolved_dependencies,
            prepared_datasets=prepared_datasets,
        ),
        status_code,
    )


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
            payload=_final_payload(
                items,
                prepared_datasets=prepared_datasets,
                dependencies=resolved_dependencies,
            ),
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
