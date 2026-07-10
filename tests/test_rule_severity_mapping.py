from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.core.validation.helpers import build_finding, severity_for_rule


def test_severity_is_derived_from_rule_id() -> None:
    finding = build_finding(
        column_name="가격",
        severity="error",
        category_group="domain_validity",
        criterion_name="amount_domain",
        message="금액 도메인 컬럼에 숫자 파싱이 되지 않는 값이 존재합니다.",
        row_indexes=[1],
    )

    assert finding.rule_id == "amount_domain"
    assert finding.severity == "warning"
    assert finding.finding_type == "issue"


def test_manual_review_rule_ids_are_info() -> None:
    finding = build_finding(
        column_name="미분류컬럼",
        severity="warning",
        category_group="completeness",
        criterion_name="required_value",
        rule_id="manual_review_required",
        message="검증 규칙이 할당되지 않아 수동 검토가 필요합니다.",
    )

    assert finding.severity == "info"
    assert finding.finding_type == "manual_review"


def test_unknown_rule_uses_valid_fallback_severity() -> None:
    assert severity_for_rule("custom_rule", fallback="error") == "error"
    assert severity_for_rule("custom_rule", fallback="invalid") == "warning"
