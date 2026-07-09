from __future__ import annotations

import csv
import math
import os
from pathlib import Path
from typing import Any

try:
    from .core.config.constants import (
        QUALITY_DETECTION_RESULTS_CSV_NAME,
        VALIDATION_OUTPUT_DIR_NAME,
    )
    from .core.reporting import write_error_report
except ImportError:  # pragma: no cover
    if __package__:
        raise
    from core.config.constants import (
        QUALITY_DETECTION_RESULTS_CSV_NAME,
        VALIDATION_OUTPUT_DIR_NAME,
    )
    from core.reporting import write_error_report


DETECTION_MATRIX_METADATA_FIELDS = [
    "dataset_name",
    "row_index",
]
PIPELINE_PROGRESS_STEPS = (
    ("load_reference_data", "입력 형식 확인"),
    ("normalize_columns", "컬럼 구조 정리"),
    ("profile_values", "데이터 프로파일링"),
    ("route_rules", "검증 기준 라우팅"),
    ("semantic_profile", "컬럼 의미 분석"),
    ("validate", "규칙 기반 검증"),
    ("categorical_semantic_validate", "정밀/문맥 검증"),
    ("propose_repairs", "수정 제안 구성"),
    ("verify_results", "최종 결과 정리"),
)
REPORT_PROGRESS_STEP = ("write_reports", "리포트 생성")
PIPELINE_PROGRESS_STEP_LABELS = dict(PIPELINE_PROGRESS_STEPS + (REPORT_PROGRESS_STEP,))


def _build_graph(
    *,
    openai_api_key: str | None,
    llm_model: str | None,
    llm_fast_model: str | None,
    llm_strong_model: str | None,
):
    try:
        from .graph import build_graph
    except ImportError:  # pragma: no cover
        if __package__:
            raise
        from graph import build_graph

    return build_graph(
        openai_api_key=openai_api_key,
        llm_model=llm_model,
        llm_fast_model=llm_fast_model,
        llm_strong_model=llm_strong_model,
    )


def validation_output_dir(base_dir: Path | None = None) -> Path:
    if os.getenv("VERCEL") and base_dir is None:
        return Path("/tmp") / VALIDATION_OUTPUT_DIR_NAME
    base = base_dir or Path(__file__).resolve().parent.parent
    return base / VALIDATION_OUTPUT_DIR_NAME


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


def _unique_column_headers(column_names: list[str]) -> list[tuple[str, str]]:
    seen: dict[str, int] = {}
    reserved = set(DETECTION_MATRIX_METADATA_FIELDS)
    used = set(reserved)
    headers = []

    for column_name in column_names:
        base = column_name.strip() or "column"
        if base in reserved:
            base = f"data_{base}"
        seen[base] = seen.get(base, 0) + 1
        header = base if seen[base] == 1 else f"{base}_{seen[base]}"
        while header in used:
            seen[base] += 1
            header = f"{base}_{seen[base]}"
        used.add(header)
        headers.append((column_name, header))

    return headers


def _detection_row_count(result: dict) -> int:
    summary = result["summary"]
    row_count = int(summary.get("row_count") or 0)
    preview_row_count = len(result.get("preview_rows") or [])
    max_finding_row_index = max(
        (
            int(row_index)
            for finding in result.get("findings", [])
            for row_index in (finding.get("row_indexes") or [])
            if str(row_index).isdigit()
        ),
        default=0,
    )
    return max(row_count, preview_row_count, max_finding_row_index)


def _detection_column_headers(result: dict) -> list[tuple[str, str]]:
    column_names = [column.get("raw_name", "") for column in result.get("columns", [])]
    if not column_names:
        column_names = list(result.get("preview_headers") or [])
    return _unique_column_headers([str(column_name) for column_name in column_names])


def _issue_cells(result: dict, column_headers: list[tuple[str, str]]) -> set[tuple[int, str]]:
    headers_by_raw_name: dict[str, list[str]] = {}
    for raw_name, header in column_headers:
        headers_by_raw_name.setdefault(raw_name, []).append(header)

    cells: set[tuple[int, str]] = set()
    for finding in result.get("findings", []):
        if finding.get("finding_type") != "issue":
            continue

        row_indexes = [
            int(row_index)
            for row_index in (finding.get("row_indexes") or [])
            if str(row_index).isdigit() and int(row_index) > 0
        ]
        if not row_indexes:
            continue

        column_name = str(finding.get("column_name") or "")
        for header in headers_by_raw_name.get(column_name, []):
            cells.update((row_index, header) for row_index in row_indexes)

    return cells


def _write_detection_result_csv(result: dict, output_dir: Path | None = None) -> str:
    summary = result["summary"]
    output_path = (output_dir or validation_output_dir()) / QUALITY_DETECTION_RESULTS_CSV_NAME
    output_path.parent.mkdir(parents=True, exist_ok=True)

    column_headers = _detection_column_headers(result)
    fieldnames = DETECTION_MATRIX_METADATA_FIELDS + [header for _, header in column_headers]
    issue_cells = _issue_cells(result, column_headers)
    row_count = _detection_row_count(result)

    with output_path.open("w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()

        for row_index in range(1, row_count + 1):
            row = {
                "dataset_name": summary.get("dataset_name", ""),
                "row_index": row_index,
            }
            for _, header in column_headers:
                row[header] = 1 if (row_index, header) in issue_cells else 0
            writer.writerow(row)

    return str(output_path)


def _write_error_report(result: dict, validation_rows: list[dict[str, str]]) -> str:
    return str(
        write_error_report(
            result=result,
            validation_rows=validation_rows,
            output_dir=validation_output_dir(),
        )
    )


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


def _pipeline_input(
    *,
    dataset_id: str | None,
    dataset_name: str | None,
    meta_csv: str | None,
    uploaded_dataset_csv: str | None,
    uploaded_dataset_name: str | None,
    use_llm_agents: bool,
    llm_model: str | None,
    llm_fast_model: str | None,
    llm_strong_model: str | None,
) -> dict[str, Any]:
    return {
        "dataset_id": dataset_id,
        "dataset_name": dataset_name,
        "meta_csv_path": str(Path(meta_csv)) if meta_csv else None,
        "uploaded_dataset_path": str(Path(uploaded_dataset_csv)) if uploaded_dataset_csv else None,
        "uploaded_dataset_name": uploaded_dataset_name,
        "use_llm_agents": use_llm_agents,
        "llm_model": llm_model,
        "llm_fast_model": llm_fast_model,
        "llm_strong_model": llm_strong_model,
    }


def _response_from_pipeline_state(result: dict) -> dict:
    response = _json_safe({
        "summary": result["summary"],
        "preview_headers": result.get("preview_headers", []),
        "preview_rows": result.get("preview_rows", []),
        "columns": [column.model_dump() for column in result["columns"]],
        "findings": _response_findings_with_row_values(result),
        "agent_traces": [trace.model_dump() for trace in result.get("agent_traces", [])],
    })
    response["summary"]["validation_result_csv"] = _write_detection_result_csv(response)
    response["summary"]["error_report_xlsx"] = _write_error_report(
        response,
        result.get("validation_rows", []),
    )
    return response


def _pipeline_progress_event(node_name: str, step_index: int, step_total: int) -> dict[str, Any]:
    label = PIPELINE_PROGRESS_STEP_LABELS.get(node_name, node_name)
    message = f"{label} 중" if node_name == REPORT_PROGRESS_STEP[0] else f"{label} 완료"
    return {
        "node": node_name,
        "stage_label": label,
        "stage_index": step_index,
        "stage_total": step_total,
        "message": message,
    }


def stream_pipeline(
    *,
    dataset_id: str | None = None,
    dataset_name: str | None = None,
    meta_csv: str | None = None,
    uploaded_dataset_csv: str | None = None,
    uploaded_dataset_name: str | None = None,
    use_llm_agents: bool = False,
    openai_api_key: str | None = None,
    llm_model: str | None = None,
    llm_fast_model: str | None = None,
    llm_strong_model: str | None = None,
):
    if not uploaded_dataset_csv and not dataset_id and not dataset_name:
        raise ValueError("uploaded_dataset_csv, dataset_id, or dataset_name 중 하나는 필요합니다.")
    if not uploaded_dataset_csv and not meta_csv:
        raise ValueError("dataset_id 또는 dataset_name으로 분석하려면 meta_csv가 필요합니다.")

    graph = _build_graph(
        openai_api_key=openai_api_key,
        llm_model=llm_model,
        llm_fast_model=llm_fast_model,
        llm_strong_model=llm_strong_model,
    )
    graph_input = _pipeline_input(
        dataset_id=dataset_id,
        dataset_name=dataset_name,
        meta_csv=meta_csv,
        uploaded_dataset_csv=uploaded_dataset_csv,
        uploaded_dataset_name=uploaded_dataset_name,
        use_llm_agents=use_llm_agents,
        llm_model=llm_model,
        llm_fast_model=llm_fast_model,
        llm_strong_model=llm_strong_model,
    )
    result_state: dict[str, Any] = dict(graph_input)
    step_positions = {node_name: index for index, (node_name, _) in enumerate(PIPELINE_PROGRESS_STEPS, start=1)}
    step_total = len(PIPELINE_PROGRESS_STEPS) + 1

    for update in graph.stream(graph_input, stream_mode="updates"):
        if not isinstance(update, dict):
            continue
        for node_name, node_update in update.items():
            if isinstance(node_update, dict):
                result_state.update(node_update)
            step_index = step_positions.get(node_name)
            if step_index is None:
                continue
            yield {
                "kind": "progress",
                **_pipeline_progress_event(node_name, step_index, step_total),
            }

    report_step_index = len(PIPELINE_PROGRESS_STEPS) + 1
    yield {
        "kind": "progress",
        **_pipeline_progress_event(REPORT_PROGRESS_STEP[0], report_step_index, step_total),
    }
    yield {
        "kind": "result",
        "result": _response_from_pipeline_state(result_state),
    }


def run_pipeline(
    *,
    dataset_id: str | None = None,
    dataset_name: str | None = None,
    meta_csv: str | None = None,
    uploaded_dataset_csv: str | None = None,
    uploaded_dataset_name: str | None = None,
    use_llm_agents: bool = False,
    openai_api_key: str | None = None,
    llm_model: str | None = None,
    llm_fast_model: str | None = None,
    llm_strong_model: str | None = None,
) -> dict:
    if not uploaded_dataset_csv and not dataset_id and not dataset_name:
        raise ValueError("uploaded_dataset_csv, dataset_id, or dataset_name 중 하나는 필요합니다.")
    if not uploaded_dataset_csv and not meta_csv:
        raise ValueError("dataset_id 또는 dataset_name으로 분석하려면 meta_csv가 필요합니다.")

    graph = _build_graph(
        openai_api_key=openai_api_key,
        llm_model=llm_model,
        llm_fast_model=llm_fast_model,
        llm_strong_model=llm_strong_model,
    )
    result = graph.invoke(
        _pipeline_input(
            dataset_id=dataset_id,
            dataset_name=dataset_name,
            meta_csv=meta_csv,
            uploaded_dataset_csv=uploaded_dataset_csv,
            uploaded_dataset_name=uploaded_dataset_name,
            use_llm_agents=use_llm_agents,
            llm_model=llm_model,
            llm_fast_model=llm_fast_model,
            llm_strong_model=llm_strong_model,
        )
    )
    return _response_from_pipeline_state(result)
