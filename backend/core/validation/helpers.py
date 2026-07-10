from __future__ import annotations

import re
from datetime import datetime
from typing import Literal, cast

from ..config.constants import VALIDATION_CRITERIA
from ..schema.models import ValidationFinding

Severity = Literal["info", "warning", "error"]

BOOLEAN_ALLOWED_VALUES = {"y", "n", "yes", "no", "true", "false", "0", "1", "예", "아니오", "유", "무"}
DATE_PATTERNS = (
    "%Y-%m-%d",
    "%Y%m%d",
    "%Y.%m.%d",
    "%Y/%m/%d",
    "%Y-%m",
    "%Y%m",
    "%Y",
    "%Y년",
    "%Y-%m-%d %H:%M:%S",
    "%Y%m%d%H%M%S",
)
TIME_ORDER_TOKENS = [
    ("시작", "종료"),
    ("개시", "종료"),
    ("접수", "처리"),
    ("등록", "수정"),
    ("생성", "수정"),
    ("발생", "종료"),
    ("출발", "도착"),
]
REFERENCE_PAIR_TOKENS = [
    ("코드", "명"),
    ("코드", "이름"),
    ("아이디", "명"),
    ("아이디", "이름"),
    ("번호", "명"),
]
SUSPICIOUS_SYMBOL_RE = re.compile(r"[�]|[ㄱ-ㅎㅏ-ㅣ]{2,}|[?!]{2,}|[#@$%^*_={}|\\]{3,}")
BROKEN_TEXT_RE = re.compile(r"[�]|[ㄱ-ㅎㅏ-ㅣ]{2,}")
PHONE_DIGIT_RE = re.compile(r"^[0-9+\-() ]+$")
MANUAL_REVIEW_RULE_IDS = {
    "manual_review_required",
    "categorical_value_manual_review",
    "categorical_value_normalization",
    "date_format_inconsistent",
    "row_context_manual_review",
}
RULE_SEVERITY_BY_RULE_ID: dict[str, Severity] = {
    "manual_review_required": "info",
    "categorical_value_manual_review": "info",
    "categorical_value_normalization": "info",
    "date_format_inconsistent": "info",
    "row_context_manual_review": "info",
    "garbled_text": "error",
    "whitespace_issue": "warning",
    "special_character_issue": "warning",
    "required_value": "warning",
    "duplicate_data": "warning",
    "date_domain": "warning",
    "number_domain": "warning",
    "boolean_domain": "warning",
    "amount_domain": "warning",
    "quantity_domain": "warning",
    "rate_domain": "warning",
    "categorical_semantic_domain": "warning",
    "categorical_value_out_of_domain": "warning",
    "categorical_value_truncated": "warning",
    "logical_consistency": "warning",
    "calculation_formula": "warning",
    "reference_relation": "warning",
    "address_region_prefix_mismatch": "warning",
    "time_sequence_consistency": "error",
    "precedence_accuracy": "warning",
}
SEVERITY_VALUES: set[str] = {"info", "warning", "error"}


def severity_for_rule(rule_id: str, fallback: str | None = None) -> Severity:
    mapped = RULE_SEVERITY_BY_RULE_ID.get(rule_id)
    if mapped:
        return mapped
    if fallback in SEVERITY_VALUES:
        return cast(Severity, fallback)
    return "warning"


def criterion_meta(category_group: str, criterion_name: str) -> tuple[str, str]:
    category = VALIDATION_CRITERIA[category_group]
    return category["label"], category["criteria"][criterion_name]


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
    category_label, criterion_description = criterion_meta(category_group, criterion_name)
    resolved_rule_id = rule_id or criterion_name
    resolved_severity = severity_for_rule(resolved_rule_id, fallback=severity)
    resolved_row_indexes = row_indexes or []
    resolved_finding_type = finding_type or (
        "manual_review"
        if resolved_severity == "info" or resolved_rule_id in MANUAL_REVIEW_RULE_IDS or not resolved_row_indexes
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


def parse_datetime(value: str) -> datetime | None:
    candidate = value.strip()
    if not candidate:
        return None
    if re.fullmatch(r"\d{4}\.0+", candidate):
        candidate = candidate.split(".", 1)[0]
    for pattern in DATE_PATTERNS:
        try:
            parsed = datetime.strptime(candidate, pattern)
            if pattern in {"%Y", "%Y년"} and not 1900 <= parsed.year <= 2200:
                return None
            return parsed
        except ValueError:
            continue
    return None


def parse_number(value: str) -> float | None:
    try:
        return float(value.replace(",", "").strip())
    except Exception:
        return None


def contains_broken_text(value: str) -> bool:
    return bool(BROKEN_TEXT_RE.search(value))


def has_whitespace_issue(value: str) -> bool:
    return value != value.strip() or bool(re.search(r"\s{2,}", value))


def has_special_char_issue(value: str) -> bool:
    return bool(SUSPICIOUS_SYMBOL_RE.search(value))
