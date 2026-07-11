from __future__ import annotations

import math
from typing import Any

from backend.application.dto import PipelineData, PipelineResult, pipeline_data, pipeline_result


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


def _response_findings_with_row_values(
    result_or_findings,
    validation_rows: list[dict[str, str]] | None = None,
) -> list[dict]:
    if validation_rows is None:
        validation_rows = pipeline_data(result_or_findings).validation_rows
        findings = pipeline_result(result_or_findings).findings
    else:
        findings = result_or_findings

    payloads = []
    for finding in findings:
        finding_payload = finding.model_dump()
        row_values = _finding_row_values(finding_payload, validation_rows)
        if row_values:
            finding_payload["row_values"] = row_values
        payloads.append(finding_payload)
    return payloads


def _response_from_pipeline_parts(data: PipelineData, pipeline_result_state: PipelineResult) -> dict:
    return _json_safe(
        {
            "summary": pipeline_result_state.summary,
            "preview_headers": data.preview_headers,
            "preview_rows": data.preview_rows,
            "columns": [column.model_dump() for column in data.columns],
            "findings": _response_findings_with_row_values(
                pipeline_result_state.findings,
                data.validation_rows,
            ),
            "agent_traces": [trace.model_dump() for trace in pipeline_result_state.agent_traces],
        }
    )


def _response_from_pipeline_state(result: dict) -> dict:
    data = pipeline_data(result)
    return _response_from_pipeline_parts(data, pipeline_result(result))
