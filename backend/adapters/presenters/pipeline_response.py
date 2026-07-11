from __future__ import annotations

import math
from typing import Any


def _json_safe(value: Any) -> Any:
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {key: _json_safe(nested_value) for key, nested_value in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    return value


def _finding_row_values(finding: dict, validation_rows: list[dict[str, str]]) -> dict[str, str]:
    column_name = str(finding.get("column_name") or "")
    if not column_name:
        return {}

    row_values: dict[str, str] = {}
    for row_index in finding.get("row_indexes") or []:
        try:
            parsed = int(row_index)
        except (TypeError, ValueError):
            continue
        if parsed <= 0 or parsed > len(validation_rows):
            continue
        row_values[str(parsed)] = validation_rows[parsed - 1].get(column_name, "")
    return row_values


def _response_findings_with_row_values(result: dict) -> list[dict]:
    validation_rows = result.get("validation_rows", [])
    findings = []
    for finding in result["findings"]:
        finding_payload = finding.model_dump()
        row_values = _finding_row_values(finding_payload, validation_rows)
        if row_values:
            finding_payload["row_values"] = row_values
        findings.append(finding_payload)
    return findings


def _response_from_pipeline_state(result: dict) -> dict:
    return _json_safe(
        {
            "summary": result["summary"],
            "preview_headers": result.get("preview_headers", []),
            "preview_rows": result.get("preview_rows", []),
            "columns": [column.model_dump() for column in result["columns"]],
            "findings": _response_findings_with_row_values(result),
            "agent_traces": [trace.model_dump() for trace in result.get("agent_traces", [])],
        }
    )


def _pipeline_progress_event(
    node_name: str,
    step_index: int,
    step_total: int,
    *,
    step_labels: dict[str, str],
    report_step_name: str,
) -> dict[str, Any]:
    label = step_labels.get(node_name, node_name)
    message = f"{label} 중" if node_name == report_step_name else f"{label} 완료"
    return {
        "node": node_name,
        "stage_label": label,
        "stage_index": step_index,
        "stage_total": step_total,
        "message": message,
    }
