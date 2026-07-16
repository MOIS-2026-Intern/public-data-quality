from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.application.services.pipeline.verification import verify_results
from backend.domain.entities.models import ColumnProfile, DatasetMeta
from backend.domain.policies.shared.helpers import build_finding


def _dataset_meta() -> DatasetMeta:
    return DatasetMeta(dataset_id="dataset", dataset_name="dataset")


def _name_column() -> ColumnProfile:
    return ColumnProfile(
        raw_name="기관명",
        normalized_name="기관명",
        source="response",
        semantic_tags=["name"],
        assigned_rules=["categorical_semantic_domain"],
        inferred_primitive_type="text",
        non_empty_count=2,
        distinct_count=2,
        sample_values=["커뮤니티센터", "문의 후 이용 바랍니다"],
        top_values=[("커뮤니티센터", 1), ("문의 후 이용 바랍니다", 1)],
    )


def test_non_whitespace_manual_review_is_filtered_by_verification() -> None:
    column = _name_column()
    raw_findings = [
        build_finding(
            column_name=column.raw_name,
            severity="info",
            category_group="domain_validity",
            criterion_name="categorical_semantic_domain",
            rule_id="categorical_value_manual_review",
            message="'문의 후 이용 바랍니다' 값은 의미 판정이 애매해 수동 검토가 필요합니다.",
            row_indexes=[2],
            related_columns=[column.raw_name],
            evidence=["confidence:0.72", "detector:llm_categorical"],
        ),
        build_finding(
            column_name=column.raw_name,
            severity="warning",
            category_group="domain_validity",
            criterion_name="categorical_semantic_domain",
            rule_id="categorical_value_out_of_domain",
            message="'문의 후 이용 바랍니다' 값은 해당 컬럼의 의미 도메인과 맞지 않을 수 있습니다.",
            row_indexes=[2],
            related_columns=[column.raw_name],
            evidence=["confidence:0.95", "stage:fast", "detector:llm_categorical"],
        ),
    ]

    result = verify_results(
        {
            "dataset_meta": _dataset_meta(),
            "columns": [column],
            "findings": raw_findings,
        }
    )

    assert result["findings"] == []
    assert result["summary"]["manual_review_finding_count"] == 0
    assert result["summary"]["issue_finding_count"] == 0
    assert result["summary"]["suppressed_potential_finding_count"] == 1


def test_manual_review_required_is_filtered_by_verification() -> None:
    column = ColumnProfile(
        raw_name="미분류컬럼",
        normalized_name="미분류컬럼",
        source="response",
        semantic_tags=[],
        assigned_rules=[],
        inferred_primitive_type="text",
        non_empty_count=1,
        distinct_count=1,
        sample_values=["값"],
        top_values=[("값", 1)],
    )
    raw_findings = [
        build_finding(
            column_name=column.raw_name,
            severity="warning",
            category_group="completeness",
            criterion_name="required_value",
            rule_id="manual_review_required",
            message="검증 규칙이 할당되지 않아 수동 검토가 필요합니다.",
        )
    ]

    result = verify_results(
        {
            "dataset_meta": _dataset_meta(),
            "columns": [column],
            "findings": raw_findings,
        }
    )

    assert result["findings"] == []
    assert result["summary"]["manual_review_count"] == 1
    assert result["summary"]["manual_review_finding_count"] == 0
    assert result["summary"]["issue_finding_count"] == 0


def test_whitespace_manual_review_survives_verification() -> None:
    column = _name_column()
    raw_findings = [
        build_finding(
            column_name=column.raw_name,
            severity="info",
            category_group="completeness",
            criterion_name="whitespace_special_characters",
            rule_id="whitespace_manual_review",
            message="값에 경미한 공백 이상이 의심되어 수동 검토가 필요합니다.",
            row_indexes=[2],
            related_columns=[column.raw_name],
            evidence=["문의  후 이용 바랍니다"],
        )
    ]

    result = verify_results(
        {
            "dataset_meta": _dataset_meta(),
            "columns": [column],
            "findings": raw_findings,
        }
    )

    assert len(result["findings"]) == 1
    assert result["findings"][0].rule_id == "whitespace_manual_review"
    assert result["findings"][0].finding_type == "manual_review"
    assert result["summary"]["manual_review_finding_count"] == 1
    assert result["summary"]["issue_finding_count"] == 0


def test_required_value_issue_survives_verification() -> None:
    column = ColumnProfile(
        raw_name="기관명",
        normalized_name="기관명",
        source="response",
        semantic_tags=["name"],
        assigned_rules=["required_value"],
        inferred_primitive_type="text",
        non_empty_count=1,
        null_count=1,
        null_ratio=0.5,
        distinct_count=1,
        sample_values=["커뮤니티센터"],
        top_values=[("커뮤니티센터", 1)],
    )
    raw_findings = [
        build_finding(
            column_name=column.raw_name,
            severity="warning",
            category_group="completeness",
            criterion_name="required_value",
            message="필수성이 높은 컬럼으로 추정되나 결측값 1건이 존재합니다.",
            row_indexes=[2],
            evidence=["null_ratio:0.5"],
        )
    ]

    result = verify_results(
        {
            "dataset_meta": _dataset_meta(),
            "columns": [column],
            "findings": raw_findings,
        }
    )

    assert len(result["findings"]) == 1
    assert result["findings"][0].rule_id == "required_value"
    assert result["findings"][0].finding_type == "issue"
    assert result["summary"]["issue_finding_count"] == 1


def test_deterministic_date_domain_issue_survives_verification() -> None:
    column = ColumnProfile(
        raw_name="등록일",
        normalized_name="등록일",
        source="response",
        semantic_tags=["date"],
        assigned_rules=["date_domain"],
        inferred_primitive_type="text",
        non_empty_count=2,
        distinct_count=2,
        sample_values=["2024-01-01", "2024-13-01"],
        top_values=[("2024-01-01", 1), ("2024-13-01", 1)],
    )
    raw_findings = [
        build_finding(
            column_name=column.raw_name,
            severity="warning",
            category_group="domain_validity",
            criterion_name="date_domain",
            message="날짜 도메인 컬럼에서 유효하지 않은 날짜 형식 또는 범위 이탈 값이 존재합니다.",
            row_indexes=[2],
            evidence=["date_parse_ratio:0.50"],
        )
    ]

    result = verify_results(
        {
            "dataset_meta": _dataset_meta(),
            "columns": [column],
            "findings": raw_findings,
        }
    )

    assert len(result["findings"]) == 1
    assert result["findings"][0].rule_id == "date_domain"
    assert result["findings"][0].finding_type == "issue"
    assert result["summary"]["issue_finding_count"] == 1


def test_equal_count_single_char_truncation_survives_verification() -> None:
    column = _name_column()
    raw_findings = [
        build_finding(
            column_name=column.raw_name,
            severity="warning",
            category_group="domain_validity",
            criterion_name="categorical_semantic_domain",
            rule_id="categorical_value_truncated",
            message="'유치' 값은 '유치원' 값의 앞부분과 일치해 입력 중 잘림 가능성이 있습니다.",
            row_indexes=[1],
            related_columns=[column.raw_name],
            evidence=[
                "matched_full_value:유치원",
                "truncated_count:1",
                "full_count:1",
                "mapping:one_to_one",
                "detector:prefix_truncation",
                "mapping:single_char_entity_completion",
            ],
        )
    ]

    result = verify_results(
        {
            "dataset_meta": _dataset_meta(),
            "columns": [column],
            "findings": raw_findings,
        }
    )

    assert len(result["findings"]) == 1
    assert result["findings"][0].rule_id == "categorical_value_truncated"
    assert result["findings"][0].finding_type == "issue"
    assert result["summary"]["issue_finding_count"] == 1


def test_equal_count_institution_suffix_truncation_survives_verification() -> None:
    column = _name_column()
    raw_findings = [
        build_finding(
            column_name=column.raw_name,
            severity="warning",
            category_group="domain_validity",
            criterion_name="categorical_semantic_domain",
            rule_id="categorical_value_truncated",
            message="'초등' 값은 '초등학교' 값의 앞부분과 일치해 입력 중 잘림 가능성이 있습니다.",
            row_indexes=[1],
            related_columns=[column.raw_name],
            evidence=[
                "matched_full_value:초등학교",
                "truncated_count:1",
                "full_count:1",
                "mapping:one_to_one",
                "detector:prefix_truncation",
                "mapping:institution_suffix_completion",
            ],
        )
    ]

    result = verify_results(
        {
            "dataset_meta": _dataset_meta(),
            "columns": [column],
            "findings": raw_findings,
        }
    )

    assert len(result["findings"]) == 1
    assert result["findings"][0].rule_id == "categorical_value_truncated"
    assert result["findings"][0].finding_type == "issue"
    assert result["summary"]["issue_finding_count"] == 1
