from __future__ import annotations

import json
from pathlib import Path

from flask import abort

from backend.infrastructure.io.sources import PreparedDataset
from backend.infrastructure.reporting.workbooks import write_batch_error_report

from .pipeline_service import (
    PIPELINE_PROGRESS_STEPS,
    REPORT_PROGRESS_STEP,
    run_pipeline,
    validation_output_dir,
)


def _analyze_prepared_dataset(
    *,
    dataset: PreparedDataset,
    use_llm_agents: bool,
    openai_api_key: str | None,
    llm_model: str | None,
    llm_fast_model: str | None,
    llm_strong_model: str | None,
) -> dict:
    return run_pipeline(
        uploaded_dataset_csv=str(dataset.path),
        uploaded_dataset_name=dataset.display_name,
        use_llm_agents=use_llm_agents,
        openai_api_key=openai_api_key,
        llm_model=llm_model,
        llm_fast_model=llm_fast_model,
        llm_strong_model=llm_strong_model,
    )


def _batch_summary(items: list[dict]) -> dict:
    successful_results = [item["result"] for item in items if item.get("ok") and item.get("result")]
    failed_count = sum(1 for item in items if not item.get("ok"))
    return {
        "dataset_count": len(items),
        "success_count": len(successful_results),
        "failed_count": failed_count,
        "row_count": sum(int(result.get("summary", {}).get("row_count") or 0) for result in successful_results),
        "finding_count": sum(int(result.get("summary", {}).get("finding_count") or 0) for result in successful_results),
        "issue_finding_count": sum(
            int(result.get("summary", {}).get("issue_finding_count") or 0) for result in successful_results
        ),
        "manual_review_finding_count": sum(
            int(result.get("summary", {}).get("manual_review_finding_count") or 0) for result in successful_results
        ),
    }


def _batch_payload(items: list[dict]) -> dict:
    summary = _batch_summary(items)
    if summary["success_count"]:
        summary["error_report_xlsx"] = str(
            write_batch_error_report(
                items=items,
                output_dir=validation_output_dir(),
            )
        )
    return {"batch": True, "summary": summary, "results": items}


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


def _report_download_path(value: str) -> Path:
    if not value:
        abort(404)
    reports_dir = (validation_output_dir() / "reports").resolve()
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = reports_dir / candidate
    resolved = candidate.resolve()
    if reports_dir not in resolved.parents and resolved != reports_dir:
        abort(404)
    if not resolved.exists() or not resolved.is_file():
        abort(404)
    return resolved


def _download_name(filename: str) -> str:
    safe_name = filename.strip()
    if not safe_name:
        safe_name = "error_report.xlsx"
    if not safe_name.lower().endswith(".xlsx"):
        safe_name = f"{safe_name}.xlsx"
    return safe_name
