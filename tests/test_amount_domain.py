from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.domain.entities.models import ColumnProfile, DatasetMeta
from backend.domain.policies.columns.rules import validate_column


def _dataset_meta() -> DatasetMeta:
    return DatasetMeta(dataset_id="dataset", dataset_name="dataset")


def _amount_column(*, values: list[str]) -> ColumnProfile:
    non_empty_values = [value for value in values if value]
    distinct_values = list(dict.fromkeys(non_empty_values))
    return ColumnProfile(
        raw_name="가격4",
        normalized_name="가격4",
        source="response",
        semantic_tags=["amount"],
        assigned_rules=["amount_domain"],
        inferred_primitive_type="text",
        non_empty_count=len(non_empty_values),
        null_count=len(values) - len(non_empty_values),
        null_ratio=round((len(values) - len(non_empty_values)) / len(values), 4) if values else None,
        distinct_count=len(distinct_values),
        sample_values=distinct_values[:5],
        top_values=[(value, 1) for value in distinct_values[:5]],
        numeric_parse_ratio=0.0,
    )


def test_amount_domain_allows_common_price_text_formats() -> None:
    values = [
        "25,000 ~ 30,000",
        "4~14만원",
        "10,000~",
        "5,000원",
        "9000(7000)",
        "무료",
        "문의",
    ]
    rows = [{"가격4": value} for value in values]

    findings = validate_column(_amount_column(values=values), _dataset_meta(), rows)

    assert [finding.rule_id for finding in findings] == []


def test_amount_domain_flags_non_price_text_values() -> None:
    values = [
        "100시간권",
        "펌",
        "콩국수",
        "5,000원",
    ]
    rows = [{"가격4": value} for value in values]

    findings = validate_column(_amount_column(values=values), _dataset_meta(), rows)

    assert len(findings) == 1
    assert findings[0].rule_id == "amount_domain"
    assert findings[0].row_indexes == [1, 2, 3]
    assert findings[0].message == "금액 도메인 컬럼에 숫자 파싱이 되지 않는 값이 존재합니다."
