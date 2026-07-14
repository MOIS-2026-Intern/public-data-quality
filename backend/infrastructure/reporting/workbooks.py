from __future__ import annotations

from pathlib import Path
from typing import Any

from openpyxl import Workbook

from backend.config.reporting import (
    BATCH_REPORT_FILENAME,
    REPORTS_DIR_NAME,
)
from .workbook_support import (
    add_issue_comment,
    auto_width as _auto_width,
    finding_current_value as _finding_current_value,
    finding_row_indexes as _finding_row_indexes,
    issue_cells_by_position as _issue_cells_by_position,
    issue_messages_by_cell as _issue_messages_by_cell,
    report_filename as _report_filename,
    result_dataset_name as _result_dataset_name,
    result_headers as _result_headers,
    style_header_row as _style_header_row,
)
from .artifacts import unique_artifact_path


def write_error_report(
    *,
    result: dict[str, Any],
    validation_rows: list[dict[str, str]],
    output_dir: Path,
) -> Path:
    reports_dir = output_dir / REPORTS_DIR_NAME
    reports_dir.mkdir(parents=True, exist_ok=True)

    dataset_name = str(result.get("summary", {}).get("dataset_name") or "dataset")
    report_path = unique_artifact_path(reports_dir, _report_filename(dataset_name))

    workbook = Workbook()
    summary_sheet = workbook.active
    summary_sheet.title = "요약"
    _write_summary_sheet(summary_sheet, result, validation_rows)
    _write_data_sheet(workbook.create_sheet("전체 데이터 오류 표시"), result, validation_rows)
    _write_findings_sheet(workbook.create_sheet("오류 상세"), result, validation_rows)

    workbook.save(report_path)
    return report_path


def write_batch_error_report(
    *,
    items: list[dict[str, Any]],
    output_dir: Path,
) -> Path:
    reports_dir = output_dir / REPORTS_DIR_NAME
    reports_dir.mkdir(parents=True, exist_ok=True)

    report_path = unique_artifact_path(reports_dir, BATCH_REPORT_FILENAME)
    workbook = Workbook()
    summary_sheet = workbook.active
    summary_sheet.title = "요약"
    successful_results = _successful_batch_results(items)
    _write_batch_summary_sheet(summary_sheet, successful_results)
    _write_batch_findings_sheet(workbook.create_sheet("오류 상세"), successful_results)

    workbook.save(report_path)
    return report_path
def _write_summary_sheet(sheet, result: dict[str, Any], validation_rows: list[dict[str, str]]) -> None:
    summary = result.get("summary", {})
    issue_cells = _issue_cells_by_position(result)
    issue_rows = {row_index for row_index, _ in issue_cells}
    issue_columns = {column_name for _, column_name in issue_cells}
    rows = [
        ("전체 컬럼 수", summary.get("column_count", 0)),
        ("전체 행 수", summary.get("row_count") or len(validation_rows)),
        ("전체 오류 발생 컬럼 수", len(issue_columns)),
        ("오류 발생 행 수", len(issue_rows)),
    ]
    sheet.append(["항목", "값"])
    for row in rows:
        sheet.append(list(row))
    _style_header_row(sheet, 1)
    _auto_width(sheet)
    sheet.freeze_panes = "A2"


def _write_data_sheet(sheet, result: dict[str, Any], validation_rows: list[dict[str, str]]) -> None:
    headers = _result_headers(result, validation_rows)
    sheet.append(["row_index", *headers])
    _style_header_row(sheet, 1)
    sheet.freeze_panes = "A2"

    issue_map = _issue_messages_by_cell(result)
    max_finding_row = max((row_index for row_index, _ in issue_map), default=0)
    row_count = max(len(validation_rows), max_finding_row)

    for row_index in range(1, row_count + 1):
        source_row = validation_rows[row_index - 1] if row_index <= len(validation_rows) else {}
        sheet.append([row_index, *[source_row.get(header, "") for header in headers]])

    column_index_by_name = {header: index + 2 for index, header in enumerate(headers)}
    for (row_index, column_name), messages in issue_map.items():
        excel_row = row_index + 1
        excel_column = column_index_by_name.get(column_name)
        if not excel_column:
            continue
        add_issue_comment(sheet, row_index=excel_row, column_index=excel_column, messages=messages)

    _auto_width(sheet, max_width=42)


def _write_findings_sheet(sheet, result: dict[str, Any], validation_rows: list[dict[str, str]]) -> None:
    headers = [
        "데이터명",
        "컬럼명",
        "행 번호",
        "현재 값",
        "오류 메세지",
        "LLM 최종 검증",
    ]
    sheet.append(headers)
    _style_header_row(sheet, 1)
    sheet.freeze_panes = "A2"

    dataset_name = str(result.get("summary", {}).get("dataset_name") or "")
    for finding in result.get("findings", []):
        if finding.get("finding_type") != "issue":
            continue
        column_name = str(finding.get("column_name") or "")
        row_indexes = _finding_row_indexes(finding)
        if not row_indexes:
            row_indexes = [None]
        for row_index in row_indexes:
            current_value = ""
            if row_index and 0 < row_index <= len(validation_rows):
                current_value = validation_rows[row_index - 1].get(column_name, "")
            sheet.append(
                [
                    dataset_name,
                    column_name,
                    row_index or "",
                    current_value,
                    finding.get("message", ""),
                    finding.get("llm_final_verification", ""),
                ]
            )

    _auto_width(sheet, max_width=48)


def _write_batch_summary_sheet(sheet, results: list[dict[str, Any]]) -> None:
    issue_cells = {
        (dataset_name, row_index, column_name)
        for result in results
        for dataset_name in [_result_dataset_name(result)]
        for row_index, column_name in _issue_cells_by_position(result)
    }
    issue_rows = {(dataset_name, row_index) for dataset_name, row_index, _ in issue_cells}
    issue_columns = {(dataset_name, column_name) for dataset_name, _, column_name in issue_cells}
    rows = [
        ("전체 데이터 개수", len(results)),
        ("전체 컬럼 수", sum(int(result.get("summary", {}).get("column_count") or 0) for result in results)),
        ("전체 행 수", sum(int(result.get("summary", {}).get("row_count") or 0) for result in results)),
        ("전체 오류 발생 컬럼 수", len(issue_columns)),
        ("오류 발생 행 수", len(issue_rows)),
    ]
    sheet.append(["항목", "값"])
    for row in rows:
        sheet.append(list(row))
    _style_header_row(sheet, 1)
    _auto_width(sheet)
    sheet.freeze_panes = "A2"


def _write_batch_findings_sheet(sheet, results: list[dict[str, Any]]) -> None:
    headers = [
        "데이터명",
        "컬럼명",
        "행 번호",
        "현재 값",
        "오류 메세지",
        "LLM 최종 검증",
    ]
    sheet.append(headers)
    _style_header_row(sheet, 1)
    sheet.freeze_panes = "A2"

    for result in results:
        dataset_name = _result_dataset_name(result)
        for finding in result.get("findings", []):
            if finding.get("finding_type") != "issue":
                continue
            column_name = str(finding.get("column_name") or "")
            row_indexes = _finding_row_indexes(finding) or [None]
            for row_index in row_indexes:
                sheet.append(
                    [
                        dataset_name,
                        column_name,
                        row_index or "",
                        _finding_current_value(finding, row_index),
                        finding.get("message", ""),
                        finding.get("llm_final_verification", ""),
                    ]
                )
    _auto_width(sheet, max_width=48)


def _successful_batch_results(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for item in items:
        if not item.get("ok") or not isinstance(item.get("result"), dict):
            continue
        result = item["result"]
        if not result.get("summary", {}).get("dataset_name"):
            result = {
                **result,
                "summary": {
                    **result.get("summary", {}),
                    "dataset_name": item.get("filename") or "dataset",
                },
            }
        results.append(result)
    return results
