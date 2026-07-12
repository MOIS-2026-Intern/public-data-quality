from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypedDict

from flask import abort

from backend.application.dto import PipelineExecutionRequest, PreparedDataset
from backend.config.pipeline import PIPELINE_PROGRESS_STEPS, REPORT_PROGRESS_STEP

from .dependencies import WebAdapterDependencies, default_web_dependencies
from .pipeline_service import PipelineRunResult, run_pipeline


class AnalysisItem(TypedDict, total=False):
    ok: bool
    filename: str
    result: dict[str, Any]
    error: str


class AnalysisPayload(TypedDict, total=False):
    batch: bool
    summary: dict[str, Any]
    results: list[AnalysisItem]
    result: dict[str, Any] | None
    error: str


def _resolve_dependencies(dependencies: WebAdapterDependencies | None) -> WebAdapterDependencies:
    return dependencies or default_web_dependencies()


def _analyze_prepared_dataset(
    *,
    dataset: PreparedDataset,
    request: PipelineExecutionRequest,
    dependencies: WebAdapterDependencies | None = None,
) -> dict:
    resolved_dependencies = _resolve_dependencies(dependencies)
    return _analysis_result_payload(
        run_pipeline(
            request=request.model_copy(
                update={
                    "uploaded_dataset_csv": str(dataset.path),
                    "uploaded_dataset_name": dataset.display_name,
                }
            ),
            dependencies=resolved_dependencies,
        ),
        dependencies=resolved_dependencies,
    )


def _analysis_result_payload(
    result: PipelineRunResult | dict[str, Any],
    *,
    dependencies: WebAdapterDependencies | None = None,
) -> dict[str, Any]:
    resolved_dependencies = _resolve_dependencies(dependencies)
    if isinstance(result, PipelineRunResult):
        return resolved_dependencies.attach_report_paths(
            response=result.response,
            validation_rows=result.validation_rows,
            output_dir=resolved_dependencies.validation_output_dir(),
        )
    return result


def _batch_summary(items: list[AnalysisItem]) -> dict[str, Any]:
    success_count = 0
    failed_count = 0
    row_count = 0
    finding_count = 0
    issue_finding_count = 0
    manual_review_finding_count = 0

    for item in items:
        result = item.get("result")
        if item.get("ok") and isinstance(result, dict):
            summary = result.get("summary") or {}
            success_count += 1
            row_count += int(summary.get("row_count") or 0)
            finding_count += int(summary.get("finding_count") or 0)
            issue_finding_count += int(summary.get("issue_finding_count") or 0)
            manual_review_finding_count += int(summary.get("manual_review_finding_count") or 0)
            continue
        failed_count += 1

    return {
        "dataset_count": len(items),
        "success_count": success_count,
        "failed_count": failed_count,
        "row_count": row_count,
        "finding_count": finding_count,
        "issue_finding_count": issue_finding_count,
        "manual_review_finding_count": manual_review_finding_count,
    }


def _analysis_payload(
    items: list[AnalysisItem],
    *,
    summary: dict[str, Any] | None = None,
) -> AnalysisPayload:
    is_batch = len(items) != 1
    if not is_batch:
        single_item = items[0] if items else {}
        single_result = single_item.get("result") if isinstance(single_item.get("result"), dict) else None
        payload: AnalysisPayload = {
            "batch": False,
            "summary": (single_result.get("summary") or {}) if isinstance(single_result, dict) else {},
            "results": items,
            "result": single_result,
        }
        if not single_result:
            payload["error"] = str(single_item.get("error") or "분석 실패")
        return payload

    aggregate_summary = summary or _batch_summary(items)
    return {
        "batch": True,
        "summary": aggregate_summary,
        "results": items,
        "result": None,
    }


def _progress_event(event_type: str, **payload) -> bytes:
    return (json.dumps({"type": event_type, **payload}, ensure_ascii=False) + "\n").encode("utf-8")


def _stage_steps(completed_stage_index: int) -> list[dict[str, str]]:
    stages = PIPELINE_PROGRESS_STEPS + (REPORT_PROGRESS_STEP,)
    total = len(stages)
    next_stage_index = completed_stage_index + 1
    return [
        {
            "id": stage_id,
            "label": label,
            "status": (
                "done"
                if index <= completed_stage_index
                else "active"
                if index == next_stage_index and completed_stage_index < total
                else "pending"
            ),
        }
        for index, (stage_id, label) in enumerate(stages, start=1)
    ]


def _report_download_path(value: str, *, dependencies: WebAdapterDependencies | None = None) -> Path:
    resolved_dependencies = _resolve_dependencies(dependencies)
    if not value:
        abort(404)
    reports_dir = (resolved_dependencies.validation_output_dir() / "reports").resolve()
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = reports_dir / candidate
    resolved = candidate.resolve()
    if reports_dir not in resolved.parents and resolved != reports_dir:
        abort(404)
    if not resolved.exists() or not resolved.is_file():
        abort(404)
    return resolved


def _download_name(filename: str, *, dependencies: WebAdapterDependencies | None = None) -> str:
    return _resolve_dependencies(dependencies).public_download_name(filename, default_suffix=".xlsx")
