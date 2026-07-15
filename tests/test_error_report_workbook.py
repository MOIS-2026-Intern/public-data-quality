from pathlib import Path
import sys

from openpyxl import load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.infrastructure.reporting.workbooks import write_batch_error_report, write_error_report


def _issue_finding(column_name: str, row_index: int, value: str, message: str) -> dict:
    return {
        "column_name": column_name,
        "finding_type": "issue",
        "category_label": "컬럼 완결성 검증",
        "row_indexes": [row_index],
        "message": message,
        "llm_final_verification": "LLM 확인 결과 오류입니다.",
        "row_values": {str(row_index): value},
    }


def _manual_review_finding(column_name: str, row_index: int, value: str, message: str) -> dict:
    return {
        "column_name": column_name,
        "finding_type": "manual_review",
        "category_label": "컬럼 특성 유효성 검증",
        "row_indexes": [row_index],
        "message": message,
        "row_values": {str(row_index): value},
    }


def test_single_error_report_uses_requested_sheets_and_detail_columns(tmp_path) -> None:
    result = {
        "summary": {"dataset_name": "화성시_어린이보호구역.csv", "column_count": 2, "row_count": 2},
        "preview_headers": ["시설명", "가격"],
        "findings": [
            _issue_finding("가격", 2, "메뉴삭제", "금액 컬럼에 금액이 아닌 값이 있습니다."),
            _manual_review_finding("시설명", 1, "A", "시설명 값은 의미 판정이 애매해 수동 검토가 필요합니다."),
        ],
    }
    validation_rows = [
        {"시설명": "A", "가격": "1000"},
        {"시설명": "B", "가격": "메뉴삭제"},
    ]

    report_path = write_error_report(result=result, validation_rows=validation_rows, output_dir=tmp_path)
    workbook = load_workbook(report_path)

    assert report_path.suffix == ".xlsx"
    assert report_path.name == "화성시_어린이보호구역.xlsx"
    assert workbook.sheetnames == ["요약", "전체 데이터 오류 표시", "오류 상세", "수동 검토 상세"]
    assert [cell.value for cell in workbook["요약"]["A"]] == [
        "항목",
        "전체 컬럼 수",
        "전체 행 수",
        "전체 오류 발생 컬럼 수",
        "오류 발생 행 수",
    ]
    assert [cell.value for cell in workbook["오류 상세"][1]] == [
        "데이터명",
        "컬럼명",
        "행 번호",
        "검증영역",
        "현재 값",
        "오류 메세지",
        "LLM 최종 검증",
    ]
    assert [cell.value for cell in workbook["오류 상세"][2]] == [
        "화성시_어린이보호구역.csv",
        "가격",
        2,
        "컬럼 완결성 검증",
        "메뉴삭제",
        "금액 컬럼에 금액이 아닌 값이 있습니다.",
        "LLM 확인 결과 오류입니다.",
    ]
    assert [cell.value for cell in workbook["수동 검토 상세"][1]] == [
        "데이터명",
        "컬럼명",
        "행 번호",
        "검증영역",
        "현재 값",
        "오류 메세지",
    ]
    assert [cell.value for cell in workbook["수동 검토 상세"][2]] == [
        "화성시_어린이보호구역.csv",
        "시설명",
        1,
        "컬럼 특성 유효성 검증",
        "A",
        "시설명 값은 의미 판정이 애매해 수동 검토가 필요합니다.",
    ]


def test_batch_error_report_has_summary_and_detail_sheets(tmp_path) -> None:
    items = [
        {
            "ok": True,
            "filename": "A.csv",
            "result": {
                "summary": {"dataset_name": "A.csv", "column_count": 2, "row_count": 2},
                "findings": [
                    _issue_finding("가격", 2, "메뉴삭제", "금액 오류"),
                    _manual_review_finding("시설명", 1, "A", "시설명은 수동 검토가 필요합니다."),
                ],
            },
        },
        {
            "ok": True,
            "filename": "B.csv",
            "result": {
                "summary": {"dataset_name": "B.csv", "column_count": 1, "row_count": 1},
                "findings": [_issue_finding("연락처", 1, "abc", "연락처 오류")],
            },
        },
    ]

    report_path = write_batch_error_report(items=items, output_dir=tmp_path)
    workbook = load_workbook(report_path)

    assert report_path.suffix == ".xlsx"
    assert report_path.name == "전체_오류_리포트.xlsx"
    assert workbook.sheetnames == ["요약", "오류 상세", "수동 검토 상세"]
    summary_values = {row[0].value: row[1].value for row in workbook["요약"].iter_rows(min_row=2, max_col=2)}
    assert summary_values == {
        "전체 데이터 개수": 2,
        "전체 컬럼 수": 3,
        "전체 행 수": 3,
        "전체 오류 발생 컬럼 수": 2,
        "전체 오류 발생 행 수": 2,
    }
    assert [cell.value for cell in workbook["오류 상세"][2]] == [
        "A.csv",
        "가격",
        2,
        "컬럼 완결성 검증",
        "메뉴삭제",
        "금액 오류",
        "LLM 확인 결과 오류입니다.",
    ]
    assert [cell.value for cell in workbook["수동 검토 상세"][1]] == [
        "데이터명",
        "컬럼명",
        "행 번호",
        "검증영역",
        "현재 값",
        "오류 메세지",
    ]
    assert [cell.value for cell in workbook["수동 검토 상세"][2]] == [
        "A.csv",
        "시설명",
        1,
        "컬럼 특성 유효성 검증",
        "A",
        "시설명은 수동 검토가 필요합니다.",
    ]
