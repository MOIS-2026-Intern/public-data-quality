from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.application.services.categorical_validation.llm_findings import apply_llm_categorical_findings
from backend.application.services.categorical_validation.row_context_results import append_row_context_findings
from backend.domain.entities.models import ColumnProfile


def test_date_format_inconsistent_flags_non_representative_format_only() -> None:
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

    assert generated == 1
    assert findings[0].rule_id == "date_format_inconsistent"
    assert findings[0].row_indexes == [6]
    assert "26.2.1." in findings[0].message
    assert "2026-02-01" not in findings[0].message


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


def test_row_context_manual_review_message_includes_value_and_reason() -> None:
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
    assert manual_generated == 1
    assert findings[0].rule_id == "row_context_manual_review"
    assert "불법주정차빈??" in findings[0].message
    assert "깨진 문자 ??" in findings[0].message
