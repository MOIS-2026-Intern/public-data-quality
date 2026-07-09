from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.core.validation.helpers import build_finding
from backend.service import _response_findings_with_row_values


def test_response_findings_include_values_beyond_preview_rows() -> None:
    validation_rows = [{"상세주소": ""} for _ in range(1004)]
    validation_rows.append({"상세주소": "1층 실제값"})
    finding = build_finding(
        column_name="상세주소",
        severity="warning",
        category_group="domain_validity",
        criterion_name="categorical_semantic_domain",
        rule_id="categorical_value_truncated",
        message="상세주소 값이 불완전할 수 있습니다.",
        row_indexes=[1005],
        related_columns=["상세주소"],
        evidence=["detector:truncated_address"],
    )

    findings = _response_findings_with_row_values(
        {
            "findings": [finding],
            "validation_rows": validation_rows,
        }
    )

    assert findings[0]["row_values"] == {"1005": "1층 실제값"}
