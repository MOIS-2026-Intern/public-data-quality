from collections import Counter
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.domain.policies.categorical import (
    allows_institution_suffix_truncation,
    allows_local_prefix_truncation,
    apply_local_categorical_findings,
)
from backend.domain.policies.categorical.truncation import find_truncated_value_pairs
from backend.domain.entities.models import ColumnProfile


def test_prefix_truncation_detects_real_cutoff_value() -> None:
    counter = Counter(
        {
            "서울시립": 1,
            "서울시립도서관": 3,
        }
    )

    assert find_truncated_value_pairs(counter) == [("서울시립", "서울시립도서관")]


def test_prefix_truncation_ignores_semantic_qualifier_suffix() -> None:
    counter = Counter(
        {
            "입산자실화": 1,
            "입산자실화추정": 5,
        }
    )

    assert find_truncated_value_pairs(counter) == []


def test_prefix_truncation_ignores_floor_qualifier_suffix() -> None:
    counter = Counter(
        {
            "커뮤니티센터": 2,
            "커뮤니티센터 1층": 5,
        }
    )

    assert find_truncated_value_pairs(counter) == []


def test_prefix_truncation_ignores_stacked_location_detail_suffix() -> None:
    counter = Counter(
        {
            "청소년수련관": 1,
            "청소년수련관 본관 3층": 4,
            "서울역": 1,
            "서울역 3번출구": 3,
        }
    )

    assert find_truncated_value_pairs(counter) == []


def test_prefix_truncation_ignores_organization_branch_suffix() -> None:
    counter = Counter(
        {
            "광복회": 1,
            "광복회 강원특별자치도지부": 4,
        }
    )

    assert find_truncated_value_pairs(counter) == []


def test_local_prefix_truncation_is_disabled_for_address_columns_even_with_name_tag() -> None:
    column = ColumnProfile(
        raw_name="상세주소",
        normalized_name="상세주소",
        source="response",
        semantic_tags=["address", "name"],
        inferred_primitive_type="text",
    )

    assert not allows_local_prefix_truncation(column)


def test_local_prefix_truncation_is_disabled_for_business_name_columns() -> None:
    column = ColumnProfile(
        raw_name="업소명",
        normalized_name="업소명",
        source="response",
        semantic_tags=["name"],
        inferred_primitive_type="text",
    )
    rows = [
        {"업소명": "동현세탁"},
        {"업소명": "동현세탁소"},
        {"업소명": "맛고을"},
        {"업소명": "맛고을식당"},
    ]
    findings = []

    counts = apply_local_categorical_findings(
        column=column,
        rows=rows,
        counter=Counter(row["업소명"] for row in rows),
        findings=findings,
    )

    assert not allows_local_prefix_truncation(column)
    assert counts.truncated_count == 0
    assert findings == []


def test_prefix_truncation_detects_single_char_entity_completion_with_competing_prefixes() -> None:
    counter = Counter(
        {
            "유치": 1,
            "유치원": 4,
            "유치반": 2,
            "초등학": 1,
            "초등학교": 5,
            "초등학생": 2,
        }
    )

    assert find_truncated_value_pairs(counter) == [
        ("유치", "유치원"),
        ("초등학", "초등학교"),
    ]


def test_prefix_truncation_detects_single_char_entity_completion_with_equal_counts() -> None:
    counter = Counter(
        {
            "유치": 1,
            "유치원": 1,
            "초등학": 1,
            "초등학교": 1,
        }
    )

    assert find_truncated_value_pairs(counter) == [
        ("유치", "유치원"),
        ("초등학", "초등학교"),
    ]


def test_prefix_truncation_detects_institution_suffix_completion_with_equal_counts() -> None:
    counter = Counter(
        {
            "초등": 1,
            "초등학교": 1,
            "유치": 1,
            "유치원": 1,
            "어린이": 1,
            "어린이집": 1,
        }
    )

    assert find_truncated_value_pairs(counter) == [
        ("어린이", "어린이집"),
        ("유치", "유치원"),
        ("초등", "초등학교"),
    ]


def test_institution_classification_column_allows_known_suffix_truncation() -> None:
    column = ColumnProfile(
        raw_name="시설유형",
        normalized_name="시설유형",
        source="response",
        semantic_tags=["enum"],
        inferred_primitive_type="text",
    )
    rows = [
        {"시설유형": "초등"},
        {"시설유형": "초등학교"},
        {"시설유형": "유치"},
        {"시설유형": "유치원"},
        {"시설유형": "어린이"},
        {"시설유형": "어린이집"},
    ]
    findings = []

    counts = apply_local_categorical_findings(
        column=column,
        rows=rows,
        counter=Counter(row["시설유형"] for row in rows),
        findings=findings,
    )

    assert not allows_local_prefix_truncation(column)
    assert allows_institution_suffix_truncation(column)
    assert counts.truncated_count == 3
    assert {finding.message for finding in findings} == {
        "'초등' 값은 '초등학교' 값의 앞부분과 일치해 입력 중 잘림 가능성이 있습니다.",
        "'유치' 값은 '유치원' 값의 앞부분과 일치해 입력 중 잘림 가능성이 있습니다.",
        "'어린이' 값은 '어린이집' 값의 앞부분과 일치해 입력 중 잘림 가능성이 있습니다.",
    }
    assert all("mapping:institution_suffix_completion" in finding.evidence for finding in findings)


def test_institution_classification_column_does_not_enable_generic_prefix_truncation() -> None:
    column = ColumnProfile(
        raw_name="시설유형",
        normalized_name="시설유형",
        source="response",
        semantic_tags=["enum"],
        inferred_primitive_type="text",
    )
    rows = [
        {"시설유형": "어린이"},
        {"시설유형": "어린이보호구역"},
    ]
    findings = []

    counts = apply_local_categorical_findings(
        column=column,
        rows=rows,
        counter=Counter(row["시설유형"] for row in rows),
        findings=findings,
    )

    assert counts.truncated_count == 0
    assert findings == []


def test_local_findings_accept_precomputed_row_indexes() -> None:
    column = ColumnProfile(
        raw_name="시설명",
        normalized_name="시설명",
        source="response",
        semantic_tags=["name"],
        inferred_primitive_type="text",
    )
    rows = [
        {"시설명": "서울시립"},
        {"시설명": "서울시립도서관"},
        {"시설명": "서울시립도서관"},
    ]
    findings = []

    counts = apply_local_categorical_findings(
        column=column,
        rows=rows,
        counter=Counter(row["시설명"] for row in rows),
        findings=findings,
        value_row_indexes={
            "서울시립": [1],
            "서울시립도서관": [2, 3],
        },
    )

    assert counts.truncated_count == 1
    assert len(findings) == 1
    assert findings[0].row_indexes == [1]
