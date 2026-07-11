from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any

from backend.config.reporting import QUALITY_DETECTION_RESULTS_CSV_NAME

from .workbooks import write_error_report


DETECTION_MATRIX_METADATA_FIELDS = [
    "dataset_name",
    "row_index",
]


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


def write_detection_result_csv(result: dict, output_dir: Path) -> str:
    summary = result["summary"]
    output_path = output_dir / QUALITY_DETECTION_RESULTS_CSV_NAME
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


def attach_report_paths(
    *,
    response: dict,
    validation_rows: list[dict[str, str]],
    output_dir: Path,
) -> dict:
    payload = _json_safe(response)
    payload["summary"]["validation_result_csv"] = write_detection_result_csv(payload, output_dir)
    payload["summary"]["error_report_xlsx"] = str(
        write_error_report(
            result=payload,
            validation_rows=validation_rows,
            output_dir=output_dir,
        )
    )
    return payload
