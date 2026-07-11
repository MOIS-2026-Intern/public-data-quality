from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.application.services.categorical_validation.address_detail import (
    address_detail_candidate_rows,
    append_llm_address_detail_findings,
)
from backend.application.services.pipeline.verification import verify_results
from backend.domain.entities.models import ColumnProfile, DatasetMeta
from backend.domain.policies.columns.rules import validate_column
from backend.domain.policies.columns.helpers import looks_incomplete_detail_address, looks_truncated_address_value


def _dataset_meta() -> DatasetMeta:
    return DatasetMeta(dataset_id="dataset", dataset_name="dataset")


def test_dash_like_detail_address_placeholders_are_not_incomplete() -> None:
    for value in ["-", "－", "–", "—", "−"]:
        assert not looks_incomplete_detail_address(value)


def test_closed_parentheses_in_address_detail_are_not_truncated() -> None:
    normal_values = [
        "다함께돌봄(반월)센터",
        "대학본부 별관 (E7-1) 101호 ESG센터",
        "신관 1층 경기도성남교육지원청 위(Wee)센터",
        "신학생회관(제2학생회관) 104호, 사회봉사센터",
        "향남복합문화센터1층 다함께돌봄(향남2)센터",
    ]

    for value in normal_values:
        assert not looks_truncated_address_value(value)


def test_unclosed_parentheses_in_address_still_truncated() -> None:
    assert looks_truncated_address_value("서울특별시 중구 세종대로 1 (어린이")


def test_incomplete_detail_address_is_only_llm_candidate_not_deterministic_issue() -> None:
    column = ColumnProfile(
        raw_name="상세주소",
        normalized_name="상세주소",
        source="response",
        semantic_tags=["address"],
        assigned_rules=["categorical_semantic_domain"],
        inferred_primitive_type="text",
        non_empty_count=4,
        distinct_count=4,
        sample_values=["가", "101동", "지하", "-"],
        top_values=[("가", 1), ("101동", 1), ("지하", 1), ("-", 1)],
    )
    rows = [
        {"상세주소": "가", "도로명주소": "서울특별시 중구 세종대로 1"},
        {"상세주소": "101동", "도로명주소": "서울특별시 중구 세종대로 2"},
        {"상세주소": "지하", "도로명주소": "서울특별시 중구 세종대로 3"},
        {"상세주소": "-", "도로명주소": "서울특별시 중구 세종대로 4"},
    ]

    findings = validate_column(column, _dataset_meta(), rows)
    related_columns, candidates = address_detail_candidate_rows(rows=rows, column=column)
    result = verify_results(
        {
            "dataset_meta": _dataset_meta(),
            "columns": [column],
            "findings": findings,
        }
    )

    assert findings == []
    assert related_columns == ["도로명주소"]
    assert [candidate["row_index"] for candidate in candidates] == [1]
    assert result["findings"] == []


def test_llm_address_detail_issue_requires_strong_high_confidence_and_specific_reason() -> None:
    rows = [{"상세주소": "덕", "도로명주소": "서울특별시 중구 세종대로 1"}]
    findings = []

    generated = append_llm_address_detail_findings(
        result={
            "_llm_model": "gpt-4o",
            "_llm_stage": "strong",
            "_llm_escalated": True,
            "address_detail_issues": [
                {
                    "row_index": 1,
                    "column_name": "상세주소",
                    "message": "",
                    "reason": "상세주소 값이 문장 중간에서 잘림",
                    "confidence": 0.95,
                },
                {
                    "row_index": 1,
                    "column_name": "상세주소",
                    "message": "",
                    "reason": "잘림 가능성이 있습니다",
                    "confidence": 0.99,
                },
            ],
        },
        rows=rows,
        column_name="상세주소",
        related_columns=["도로명주소"],
        candidate_row_indexes={1},
        findings=findings,
    )

    assert generated == 1
    assert len(findings) == 1
    assert findings[0].rule_id == "categorical_value_truncated"
    assert findings[0].row_indexes == [1]
    assert "detector:llm_incomplete_detail_address" in findings[0].evidence


def test_llm_address_detail_issue_rejects_fast_stage_or_low_confidence() -> None:
    rows = [{"상세주소": "덕", "도로명주소": "서울특별시 중구 세종대로 1"}]

    for stage, confidence in [("fast", 0.99), ("strong", 0.94)]:
        findings = []
        generated = append_llm_address_detail_findings(
            result={
                "_llm_model": "model",
                "_llm_stage": stage,
                "_llm_escalated": stage == "strong",
                "address_detail_issues": [
                    {
                        "row_index": 1,
                        "column_name": "상세주소",
                        "message": "",
                        "reason": "상세주소 값이 문장 중간에서 잘림",
                        "confidence": confidence,
                    }
                ],
            },
            rows=rows,
            column_name="상세주소",
            related_columns=["도로명주소"],
            candidate_row_indexes={1},
            findings=findings,
        )

        assert generated == 0
        assert findings == []


def test_truncated_address_survives_verification() -> None:
    column = ColumnProfile(
        raw_name="주소",
        normalized_name="주소",
        source="response",
        semantic_tags=["address"],
        assigned_rules=["categorical_semantic_domain"],
        inferred_primitive_type="text",
        non_empty_count=2,
        distinct_count=2,
        sample_values=["서울특별시 중구 세종대로 1 (어린이", "서울특별시 중구 세종대로 2"],
        top_values=[
            ("서울특별시 중구 세종대로 1 (어린이", 1),
            ("서울특별시 중구 세종대로 2", 1),
        ],
    )
    rows = [
        {"주소": "서울특별시 중구 세종대로 1 (어린이"},
        {"주소": "서울특별시 중구 세종대로 2"},
    ]

    findings = validate_column(column, _dataset_meta(), rows)
    result = verify_results(
        {
            "dataset_meta": _dataset_meta(),
            "columns": [column],
            "findings": findings,
        }
    )

    assert len(findings) == 1
    assert findings[0].evidence == [
        "truncated_address_rows:1",
        "detector:truncated_address",
    ]
    assert len(result["findings"]) == 1
    assert result["findings"][0].rule_id == "categorical_value_truncated"
    assert result["findings"][0].row_indexes == [1]
