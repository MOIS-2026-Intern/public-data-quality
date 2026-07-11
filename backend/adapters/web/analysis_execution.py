from __future__ import annotations

import traceback
from collections.abc import Callable, Iterator
from typing import Any

from backend.config.pipeline import PIPELINE_PROGRESS_STEPS, REPORT_PROGRESS_STEP
from backend.infrastructure.io.sources import PreparedDataset

from .analysis_support import (
    AnalysisItem,
    AnalysisPayload,
    _analyze_prepared_dataset,
    _analysis_payload,
    _batch_summary,
    _progress_event,
    _stage_steps,
)
from .pipeline_service import stream_pipeline

AnalysisOptions = dict[str, Any]

__all__ = [
    "analyze_prepared_datasets",
    "analyze_batch_prepared_datasets",
    "stream_analysis_events",
]


def analyze_prepared_datasets(
    *,
    prepared_datasets: list[PreparedDataset],
    options: AnalysisOptions,
) -> tuple[AnalysisPayload, int]:
    items = [_analyze_dataset_item(dataset=dataset, options=options) for dataset in prepared_datasets]
    summary = _batch_summary(items)
    status_code = 200 if summary["success_count"] else 400
    return _analysis_payload(items, summary=summary), status_code


def analyze_batch_prepared_datasets(
    *,
    prepared_datasets: list[PreparedDataset],
    options: AnalysisOptions,
) -> tuple[AnalysisPayload, int]:
    return analyze_prepared_datasets(prepared_datasets=prepared_datasets, options=options)


def stream_analysis_events(
    *,
    prepared_datasets: list[PreparedDataset],
    options: AnalysisOptions,
    cleanup: Callable[[], None],
) -> Iterator[bytes]:
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
                traceback.print_exc()
                items.append(_error_item(dataset.display_name, exc))
                yield _dataset_finished_event(
                    event_type="file_error",
                    index=index,
                    total_files=total_files,
                    filename=dataset.display_name,
                    message="실패",
                    final_stage_index=final_stage_index,
                    error=str(exc) or exc.__class__.__name__,
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
) -> AnalysisItem:
    try:
        result = _analyze_prepared_dataset(dataset=dataset, **options)
        return _success_item(dataset.display_name, result)
    except Exception as exc:  # pragma: no cover
        traceback.print_exc()
        return _error_item(dataset.display_name, exc)


def _stream_dataset_events(
    *,
    index: int,
    total_files: int,
    dataset: PreparedDataset,
    options: AnalysisOptions,
) -> Iterator[bytes]:
    result = None
    for pipeline_event in stream_pipeline(
        uploaded_dataset_csv=str(dataset.path),
        uploaded_dataset_name=dataset.display_name,
        **options,
    ):
        if pipeline_event.get("kind") == "result":
            result = pipeline_event.get("result")
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


def _error_item(filename: str, exc: Exception) -> AnalysisItem:
    return {
        "ok": False,
        "filename": filename,
        "error": str(exc) or exc.__class__.__name__,
    }
