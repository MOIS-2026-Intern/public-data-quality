from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.application.services.categorical_validation.llm_findings import apply_llm_categorical_findings
from backend.application.services.categorical_validation.row_context_results import append_row_context_findings
from backend.domain.entities.models import ColumnProfile


def test_date_format_inconsistent_result_is_ignored() -> None:
    column = ColumnProfile(
        raw_name="데이터기준일자",
        normalized_name="데이터기준일자",
        source="response",
        semantic_tags=["date"],
        assigned_rules=["date_domain"],
        inferred_primitive_type="date",
        non_empty_count=6,
        distinct_count=2,
        sample_values=["2026-02-01", "26.2.1."],
        top_values=[("2026-02-01", 5), ("26.2.1.", 1)],
    )
    rows = [
        {"데이터기준일자": "2026-02-01"},
        {"데이터기준일자": "2026-02-01"},
        {"데이터기준일자": "2026-02-01"},
        {"데이터기준일자": "2026-02-01"},
        {"데이터기준일자": "2026-02-01"},
        {"데이터기준일자": "26.2.1."},
    ]
    result = {
        "domain_label": "date",
        "inconsistent_format_groups": [
            {
                "values": ["2026-02-01", "26.2.1."],
                "target_format": "YYYY-MM-DD",
                "reason": "날짜 형식이 혼용됩니다.",
                "confidence": 0.95,
            }
        ],
        "_llm_model": "test",
        "_llm_stage": "strong",
        "_llm_escalated": True,
    }
    findings = []

    generated = apply_llm_categorical_findings(
        column=column,
        rows=rows,
        result=result,
        findings=findings,
    )

    assert generated == 0
    assert findings == []


def test_llm_categorical_truncated_text_findings_are_ignored_for_names() -> None:
    column = ColumnProfile(
        raw_name="업소명",
        normalized_name="업소명",
        source="response",
        semantic_tags=["name"],
        assigned_rules=["categorical_semantic_domain"],
        inferred_primitive_type="text",
        non_empty_count=2,
        distinct_count=2,
        sample_values=["동현세탁", "동현세탁소"],
        top_values=[("동현세탁", 1), ("동현세탁소", 1)],
    )
    rows = [
        {"업소명": "동현세탁"},
        {"업소명": "동현세탁소"},
    ]
    result = {
        "domain_label": "상호명",
        "invalid_format_values": [
            {
                "value": "동현세탁",
                "issue_type": "truncated_text",
                "reason": "세탁소 접미사가 누락된 것으로 보입니다",
                "confidence": 0.99,
            }
        ],
        "_llm_model": "test",
        "_llm_stage": "strong",
        "_llm_escalated": True,
    }
    findings = []

    generated = apply_llm_categorical_findings(
        column=column,
        rows=rows,
        result=result,
        findings=findings,
    )

    assert generated == 0
    assert findings == []


def test_row_context_manual_review_result_is_ignored() -> None:
    rows = [{"위험요인": "불법주정차빈??"}]
    columns = [{"raw_name": "위험요인", "normalized_name": "위험요인"}]
    result = {
        "row_context_manual_reviews": [
            {
                "row_index": 1,
                "column_name": "위험요인",
                "related_columns": ["위험요인"],
                "message": "'위험요인' 값은 행 문맥상 수동 검토가 필요합니다.",
                "reason": "깨진 문자 ??가 포함되어 위험요인 설명이 불완전함",
                "confidence": 0.72,
            }
        ],
        "_llm_model": "test",
        "_llm_stage": "strong",
        "_llm_escalated": True,
    }
    findings = []

    generated, manual_generated = append_row_context_findings(
        result=result,
        rows=rows,
        columns=columns,
        findings=findings,
    )

    assert generated == 0
    assert manual_generated == 0
    assert findings == []


def test_row_context_manual_review_skips_when_total_matches_multiple_components() -> None:
    rows = [
        {
            "지급건수합계(건)": "19",
            "주택지급건수(건)": "6",
            "온실지급건수(건)": "8",
            "소상공인 지급건수(건)": "5",
        }
    ]
    columns = [
        {"raw_name": "지급건수합계(건)", "normalized_name": "지급건수합계(건)"},
        {"raw_name": "주택지급건수(건)", "normalized_name": "주택지급건수(건)"},
        {"raw_name": "온실지급건수(건)", "normalized_name": "온실지급건수(건)"},
        {"raw_name": "소상공인 지급건수(건)", "normalized_name": "소상공인 지급건수(건)"},
    ]
    result = {
        "row_context_manual_reviews": [
            {
                "row_index": 1,
                "column_name": "지급건수합계(건)",
                "related_columns": [
                    "지급건수합계(건)",
                    "주택지급건수(건)",
                    "온실지급건수(건)",
                    "소상공인 지급건수(건)",
                ],
                "message": "지급건수합계와 지급건수 세부 항목 합계가 일치하지 않음",
                "reason": "합계와 세부 건수 합산 결과가 다르게 보입니다.",
                "confidence": 0.72,
            }
        ],
        "_llm_model": "test",
        "_llm_stage": "strong",
        "_llm_escalated": True,
    }
    findings = []

    generated, manual_generated = append_row_context_findings(
        result=result,
        rows=rows,
        columns=columns,
        findings=findings,
    )

    assert generated == 0
    assert manual_generated == 0
    assert findings == []


def test_row_context_manual_review_ignores_total_mismatch_manual_review() -> None:
    rows = [
        {
            "지급건수합계(건)": "20",
            "주택지급건수(건)": "6",
            "온실지급건수(건)": "8",
            "소상공인 지급건수(건)": "5",
        }
    ]
    columns = [
        {"raw_name": "지급건수합계(건)", "normalized_name": "지급건수합계(건)"},
        {"raw_name": "주택지급건수(건)", "normalized_name": "주택지급건수(건)"},
        {"raw_name": "온실지급건수(건)", "normalized_name": "온실지급건수(건)"},
        {"raw_name": "소상공인 지급건수(건)", "normalized_name": "소상공인 지급건수(건)"},
    ]
    result = {
        "row_context_manual_reviews": [
            {
                "row_index": 1,
                "column_name": "지급건수합계(건)",
                "related_columns": [
                    "지급건수합계(건)",
                    "주택지급건수(건)",
                    "온실지급건수(건)",
                    "소상공인 지급건수(건)",
                ],
                "message": "지급건수합계와 지급건수 세부 항목 합계가 일치하지 않음",
                "reason": "합계와 세부 건수 합산 결과가 다르게 보입니다.",
                "confidence": 0.72,
            }
        ],
        "_llm_model": "test",
        "_llm_stage": "strong",
        "_llm_escalated": True,
    }
    findings = []

    generated, manual_generated = append_row_context_findings(
        result=result,
        rows=rows,
        columns=columns,
        findings=findings,
    )

    assert generated == 0
    assert manual_generated == 0
    assert findings == []


def test_row_context_manual_review_skips_uniqueness_only_message() -> None:
    rows = [{"시도": "서 울"}]
    columns = [{"raw_name": "시도", "normalized_name": "시도"}]
    result = {
        "row_context_manual_reviews": [
            {
                "row_index": 1,
                "column_name": "시도",
                "related_columns": ["시도"],
                "message": "시도에 유일한 값 '서 울'을 포함하고 있습니다.",
                "reason": "유일한 값이라 추가 확인이 필요합니다.",
                "confidence": 0.72,
            }
        ],
        "_llm_model": "test",
        "_llm_stage": "strong",
        "_llm_escalated": True,
    }
    findings = []

    generated, manual_generated = append_row_context_findings(
        result=result,
        rows=rows,
        columns=columns,
        findings=findings,
    )

    assert generated == 0
    assert manual_generated == 0
    assert findings == []


def test_row_context_manual_review_skips_sido_spacing_style_message() -> None:
    rows = [{"시도": "서 울"}]
    columns = [{"raw_name": "시도", "normalized_name": "시도"}]
    result = {
        "row_context_manual_reviews": [
            {
                "row_index": 1,
                "column_name": "시도",
                "related_columns": ["시도"],
                "message": "'시도' 값이 '서 울'로 표기되었습니다.",
                "reason": "시도 표기가 일반적인 띄어쓰기와 다릅니다.",
                "confidence": 0.72,
            }
        ],
        "_llm_model": "test",
        "_llm_stage": "strong",
        "_llm_escalated": True,
    }
    findings = []

    generated, manual_generated = append_row_context_findings(
        result=result,
        rows=rows,
        columns=columns,
        findings=findings,
    )

    assert generated == 0
    assert manual_generated == 0
    assert findings == []


def test_row_context_manual_review_skips_sido_spacing_generic_special_message() -> None:
    rows = [{"시도": "서 울"}]
    columns = [{"raw_name": "시도", "normalized_name": "시도"}]
    result = {
        "row_context_manual_reviews": [
            {
                "row_index": 1,
                "column_name": "시도",
                "related_columns": ["시도"],
                "message": "'서 울' 특이함",
                "reason": "",
                "confidence": 0.72,
            }
        ],
        "_llm_model": "test",
        "_llm_stage": "strong",
        "_llm_escalated": True,
    }
    findings = []

    generated, manual_generated = append_row_context_findings(
        result=result,
        rows=rows,
        columns=columns,
        findings=findings,
    )

    assert generated == 0
    assert manual_generated == 0
    assert findings == []


def test_row_context_manual_review_skips_generic_value_only_review_message() -> None:
    rows = [{"온실지급건수(건)": "247"}]
    columns = [{"raw_name": "온실지급건수(건)", "normalized_name": "온실지급건수(건)"}]
    result = {
        "row_context_manual_reviews": [
            {
                "row_index": 1,
                "column_name": "온실지급건수(건)",
                "related_columns": ["온실지급건수(건)"],
                "message": "'온실지급건수(건)' 값이 '247'인 경우 검토.",
                "reason": "",
                "confidence": 0.72,
            }
        ],
        "_llm_model": "test",
        "_llm_stage": "strong",
        "_llm_escalated": True,
    }
    findings = []

    generated, manual_generated = append_row_context_findings(
        result=result,
        rows=rows,
        columns=columns,
        findings=findings,
    )

    assert generated == 0
    assert manual_generated == 0
    assert findings == []
