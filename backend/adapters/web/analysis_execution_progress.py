from __future__ import annotations

from typing import Any

from backend.application.dto import PreparedDataset
from backend.config.pipeline import PIPELINE_PROGRESS_STEPS, REPORT_PROGRESS_STEP

from .analysis_support import (
    AnalysisItem,
    AnalysisPayload,
    _analysis_payload,
    _attach_batch_report_path,
    _progress_event,
    _stage_steps,
)
from .dependencies import WebAdapterDependencies


def pipeline_progress_payload(
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
        stages=_stage_steps(_completed_stage_index(pipeline_event, stage_index)),
        message=pipeline_event.get("message", "분석 중"),
    )


def dataset_started_event(
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


def dataset_finished_event(
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


def final_payload(
    items: list[AnalysisItem],
    *,
    prepared_datasets: list[PreparedDataset],
    dependencies: WebAdapterDependencies,
) -> AnalysisPayload:
    return _attach_batch_report_path(
        _analysis_payload(items),
        items=items,
        dependencies=dependencies,
        prepared_datasets=prepared_datasets,
    )


def _completed_stage_index(pipeline_event: dict[str, Any], stage_index: int) -> int:
    if pipeline_event.get("node") == REPORT_PROGRESS_STEP[0]:
        return stage_index - 1
    return stage_index
