from collections import Counter
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.application.services.categorical_validation.llm_findings import apply_llm_categorical_findings
from backend.application.services.categorical_validation.row_context_results import append_row_context_findings
from backend.domain.entities.models import ColumnProfile
from backend.domain.policies.categorical import apply_local_categorical_findings
from backend.domain.policies.categorical.column import looks_sido_column


def _sido_column() -> ColumnProfile:
    return ColumnProfile(
        raw_name="시도",
        normalized_name="시도",
        source="response",
        semantic_tags=["enum", "name"],
        assigned_rules=["categorical_semantic_domain"],
        inferred_primitive_type="text",
        non_empty_count=41,
        distinct_count=3,
        sample_values=["서울", "서 울", "부산"],
        top_values=[("서울", 38), ("서 울", 2), ("부산", 1)],
    )


def test_local_sido_spacing_variant_under_five_percent_is_ignored() -> None:
    column = _sido_column()
    rows = [{"시도": "서울"} for _ in range(38)] + [{"시도": "서 울"} for _ in range(2)] + [{"시도": "부산"}]
    findings = []

    counts = apply_local_categorical_findings(
        column=column,
        rows=rows,
        counter=Counter(row["시도"] for row in rows),
        findings=findings,
    )

    assert counts.normalization_count == 0
    assert findings == []


def test_llm_sido_spacing_manual_review_under_five_percent_is_ignored() -> None:
    column = _sido_column()
    rows = [{"시도": "서울"} for _ in range(38)] + [{"시도": "서 울"} for _ in range(2)] + [{"시도": "부산"}]
    result = {
        "domain_label": "시도",
        "needs_manual_review": [
            {
                "value": "서 울",
                "reason": "대표 표기와 달라 의미 판정이 애매합니다.",
                "confidence": 0.72,
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


def test_row_context_sido_spacing_manual_review_under_five_percent_is_ignored() -> None:
    rows = [{"시도": "서울"} for _ in range(20)] + [{"시도": "충 북"}]
    columns = [{"raw_name": "시도", "normalized_name": "시도"}]
    result = {
        "row_context_manual_reviews": [
            {
                "row_index": 21,
                "column_name": "시도",
                "related_columns": ["시도"],
                "message": "시도의 값이 '충 북'로 제공되었습니다.",
                "reason": "시도 표기가 일반적인 띄어쓰기와 다릅니다.",
                "confidence": 0.71,
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


def test_local_sido_spacing_variants_overall_ratio_over_five_percent_are_not_ignored() -> None:
    column = ColumnProfile(
        raw_name="시도",
        normalized_name="시도",
        source="response",
        semantic_tags=["enum", "name"],
        assigned_rules=["categorical_semantic_domain"],
        inferred_primitive_type="text",
        non_empty_count=55,
        distinct_count=6,
        sample_values=["서울", "서 울", "충북", "충 북", "경남", "경 남"],
        top_values=[("서울", 40), ("충북", 7), ("경남", 5), ("서 울", 1), ("충 북", 1)],
    )
    rows = (
        [{"시도": "서울"} for _ in range(40)]
        + [{"시도": "충북"} for _ in range(7)]
        + [{"시도": "경남"} for _ in range(5)]
        + [{"시도": "서 울"}]
        + [{"시도": "충 북"}]
        + [{"시도": "경 남"}]
    )
    findings = []

    apply_local_categorical_findings(
        column=column,
        rows=rows,
        counter=Counter(row["시도"] for row in rows),
        findings=findings,
    )

    assert {finding.message for finding in findings} == {
        "'서 울' 값은 '서울'로 표면 형식을 표준화하는 것이 적절합니다.",
        "'충 북' 값은 '충북'로 표면 형식을 표준화하는 것이 적절합니다.",
        "'경 남' 값은 '경남'로 표면 형식을 표준화하는 것이 적절합니다.",
    }


def test_local_sido_spacing_variant_counts_follow_emitted_findings() -> None:
    column = ColumnProfile(
        raw_name="시도",
        normalized_name="시도",
        source="response",
        semantic_tags=["enum", "name"],
        assigned_rules=["categorical_semantic_domain"],
        inferred_primitive_type="text",
        non_empty_count=55,
        distinct_count=6,
        sample_values=["서울", "서 울", "충북", "충 북", "경남", "경 남"],
        top_values=[("서울", 40), ("충북", 7), ("경남", 5), ("서 울", 1), ("충 북", 1)],
    )
    rows = (
        [{"시도": "서울"} for _ in range(40)]
        + [{"시도": "충북"} for _ in range(7)]
        + [{"시도": "경남"} for _ in range(5)]
        + [{"시도": "서 울"}]
        + [{"시도": "충 북"}]
        + [{"시도": "경 남"}]
    )
    findings = []

    counts = apply_local_categorical_findings(
        column=column,
        rows=rows,
        counter=Counter(row["시도"] for row in rows),
        findings=findings,
    )

    assert counts.normalization_count == 3
    assert counts.has_findings is True
    assert len(findings) == 3


def test_looks_sido_column_does_not_match_attempt_count_columns() -> None:
    column = ColumnProfile(
        raw_name="시도횟수",
        normalized_name="시도횟수",
        source="response",
        semantic_tags=["count"],
        assigned_rules=["categorical_semantic_domain"],
        inferred_primitive_type="text",
        non_empty_count=2,
        distinct_count=2,
        sample_values=["1", "2"],
        top_values=[("1", 1), ("2", 1)],
    )

    assert looks_sido_column(column) is False


def test_llm_sido_spacing_manual_reviews_overall_ratio_over_five_percent_are_not_ignored() -> None:
    column = ColumnProfile(
        raw_name="시도",
        normalized_name="시도",
        source="response",
        semantic_tags=["enum", "name"],
        assigned_rules=["categorical_semantic_domain"],
        inferred_primitive_type="text",
        non_empty_count=100,
        distinct_count=4,
        sample_values=["서울", "서 울", "충북", "충 북"],
        top_values=[("서울", 82), ("충북", 12), ("서 울", 3), ("충 북", 3)],
    )
    rows = (
        [{"시도": "서울"} for _ in range(82)]
        + [{"시도": "충북"} for _ in range(12)]
        + [{"시도": "서 울"} for _ in range(3)]
        + [{"시도": "충 북"} for _ in range(3)]
    )
    result = {
        "domain_label": "시도",
        "needs_manual_review": [
            {"value": "서 울", "reason": "대표 표기와 달라 의미 판정이 애매합니다.", "confidence": 0.72},
            {"value": "충 북", "reason": "대표 표기와 달라 의미 판정이 애매합니다.", "confidence": 0.72},
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

    assert generated == 2
    assert [finding.message for finding in findings] == [
        "'서 울' 값은 의미 판정이 애매해 수동 검토가 필요합니다.",
        "'충 북' 값은 의미 판정이 애매해 수동 검토가 필요합니다.",
    ]


def test_llm_sido_spacing_manual_reviews_are_ignored_when_column_uses_only_spaced_style() -> None:
    column = ColumnProfile(
        raw_name="시도",
        normalized_name="시도",
        source="response",
        semantic_tags=["enum", "name"],
        assigned_rules=["categorical_semantic_domain"],
        inferred_primitive_type="text",
        non_empty_count=4,
        distinct_count=4,
        sample_values=["서 울", "부 산", "대 구", "인 천"],
        top_values=[("서 울", 1), ("부 산", 1), ("대 구", 1), ("인 천", 1)],
    )
    rows = [{"시도": "서 울"}, {"시도": "부 산"}, {"시도": "대 구"}, {"시도": "인 천"}]
    result = {
        "domain_label": "시도",
        "needs_manual_review": [
            {"value": "서 울", "reason": "대표 표기와 달라 의미 판정이 애매합니다.", "confidence": 0.72},
            {"value": "부 산", "reason": "대표 표기와 달라 의미 판정이 애매합니다.", "confidence": 0.72},
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


def test_row_context_sido_spacing_manual_reviews_are_skipped_even_when_common() -> None:
    rows = (
        [{"시도": "서울"} for _ in range(16)]
        + [{"시도": "서 울"}]
        + [{"시도": "충 북"}]
        + [{"시도": "부산"} for _ in range(2)]
    )
    columns = [{"raw_name": "시도", "normalized_name": "시도"}]
    result = {
        "row_context_manual_reviews": [
            {
                "row_index": 17,
                "column_name": "시도",
                "related_columns": ["시도"],
                "message": "시도 값이 '서 울'로 기록되어 있습니다.",
                "reason": "시도 표기가 일반적인 띄어쓰기와 다릅니다.",
                "confidence": 0.71,
            },
            {
                "row_index": 18,
                "column_name": "시도",
                "related_columns": ["시도"],
                "message": "시도 값이 '충 북'로 기록되어 있습니다.",
                "reason": "시도 표기가 일반적인 띄어쓰기와 다릅니다.",
                "confidence": 0.71,
            },
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
