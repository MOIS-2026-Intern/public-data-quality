from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.core.pipeline.verification import verify_results
from backend.core.schema.models import ColumnProfile, DatasetMeta
from backend.core.validation.columns.rules import validate_column


def _dataset_meta() -> DatasetMeta:
    return DatasetMeta(dataset_id="dataset", dataset_name="dataset")


def test_incomplete_detail_address_survives_verification() -> None:
    column = ColumnProfile(
        raw_name="상세주소",
        normalized_name="상세주소",
        source="response",
        semantic_tags=["address"],
        assigned_rules=["categorical_semantic_domain"],
        inferred_primitive_type="text",
        non_empty_count=2,
        distinct_count=2,
        sample_values=["가", "101동"],
        top_values=[("가", 1), ("101동", 1)],
    )
    rows = [
        {"상세주소": "가", "도로명주소": "서울특별시 중구 세종대로 1"},
        {"상세주소": "101동", "도로명주소": "서울특별시 중구 세종대로 2"},
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
        "incomplete_detail_address_rows:1",
        "detector:incomplete_detail_address",
    ]
    assert len(result["findings"]) == 1
    assert result["findings"][0].rule_id == "categorical_value_truncated"
    assert result["findings"][0].row_indexes == [1]


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
