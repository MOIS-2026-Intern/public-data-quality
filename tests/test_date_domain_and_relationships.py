from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.core.schema.models import ColumnProfile, DatasetMeta
from backend.core.validation.columns.rules import validate_column
from backend.core.validation.relationships import validate_dataset_relationships


def _dataset_meta() -> DatasetMeta:
    return DatasetMeta(dataset_id="dataset", dataset_name="dataset")


def test_date_domain_allows_day_of_month_distribution() -> None:
    values = ["27", "26", "21", "17", "18", "27", "3", "10", "23", "5"]
    column = ColumnProfile(
        raw_name="종료일",
        normalized_name="종료일",
        source="response",
        semantic_tags=["date"],
        assigned_rules=["date_domain"],
        inferred_primitive_type="text",
        non_empty_count=len(values),
        distinct_count=len(set(values)),
        sample_values=values,
        top_values=[(value, 1) for value in values],
        date_parse_ratio=0.0,
    )
    rows = [{"종료일": value} for value in values]

    findings = validate_column(column, _dataset_meta(), rows)

    assert [finding.rule_id for finding in findings] == []


def test_calculation_formula_relationships_are_disabled() -> None:
    columns = [
        ColumnProfile(
            raw_name="계획인원",
            normalized_name="계획인원",
            source="response",
            semantic_tags=["count"],
            assigned_rules=["calculation_formula"],
            inferred_primitive_type="numeric",
            non_empty_count=2,
            distinct_count=2,
            sample_values=["10", "20"],
        ),
        ColumnProfile(
            raw_name="수료인원",
            normalized_name="수료인원",
            source="response",
            semantic_tags=["count"],
            assigned_rules=["calculation_formula"],
            inferred_primitive_type="numeric",
            non_empty_count=2,
            distinct_count=2,
            sample_values=["5", "10"],
        ),
        ColumnProfile(
            raw_name="기수",
            normalized_name="기수",
            source="response",
            semantic_tags=["count"],
            assigned_rules=["calculation_formula"],
            inferred_primitive_type="numeric",
            non_empty_count=2,
            distinct_count=2,
            sample_values=["1", "2"],
        ),
    ]
    rows = [
        {"계획인원": "10", "수료인원": "5", "기수": "1"},
        {"계획인원": "20", "수료인원": "10", "기수": "2"},
    ]
    candidates = [
        {
            "rule_id": "calculation_formula",
            "columns": ["계획인원", "수료인원", "기수"],
            "confidence": 0.99,
        }
    ]

    findings = validate_dataset_relationships(columns, rows, candidates)

    assert [finding.rule_id for finding in findings] == []
