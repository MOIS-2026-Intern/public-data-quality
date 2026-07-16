from __future__ import annotations

from typing import Literal, cast

from backend.domain.entities.models import ValidationFinding
from .settings import (
    MANUAL_REVIEW_RULE_IDS,
    RULE_SEVERITY_BY_RULE_ID,
    SEVERITY_VALUES,
    VALIDATION_CRITERIA,
)

Severity = Literal["info", "warning", "error"]


def build_finding(
    *,
    column_name: str,
    severity: str,
    category_group: str,
    criterion_name: str,
    message: str,
    finding_type: str | None = None,
    rule_id: str | None = None,
    row_indexes: list[int] | None = None,
    related_columns: list[str] | None = None,
    evidence: list[str] | None = None,
) -> ValidationFinding:
    category_label, criterion_description = _criterion_meta(category_group, criterion_name)
    resolved_rule_id = rule_id or criterion_name
    resolved_severity = severity_for_rule(resolved_rule_id, fallback=severity)
    resolved_row_indexes = row_indexes or []
    resolved_finding_type = finding_type or (
        "manual_review"
        if resolved_severity == "info" or resolved_rule_id in MANUAL_REVIEW_RULE_IDS
        else "issue"
    )
    display_label = "수동 검토 필요" if resolved_finding_type == "manual_review" else "오류/이상 탐지"
    return ValidationFinding(
        column_name=column_name,
        severity=resolved_severity,
        finding_type=resolved_finding_type,
        display_label=display_label,
        category_group=category_group,
        category_label=category_label,
        criterion_name=criterion_name,
        criterion_description=criterion_description,
        rule_id=resolved_rule_id,
        message=message,
        row_indexes=resolved_row_indexes,
        related_columns=related_columns or [],
        evidence=evidence or [],
    )


def severity_for_rule(rule_id: str, fallback: str | None = None) -> Severity:
    mapped = RULE_SEVERITY_BY_RULE_ID.get(rule_id)
    if mapped:
        return mapped
    if fallback in SEVERITY_VALUES:
        return cast(Severity, fallback)
    return "warning"


def _criterion_meta(category_group: str, criterion_name: str) -> tuple[str, str]:
    category = VALIDATION_CRITERIA[category_group]
    return category["label"], category["criteria"][criterion_name]


__all__ = [
    "build_finding",
    "severity_for_rule",
]
