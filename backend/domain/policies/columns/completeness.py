from __future__ import annotations

from backend.domain.entities.models import ValidationFinding
from ..shared.settings import (
    REQUIRED_VALUE_NON_UNIQUE_NAME_TOKENS,
    REQUIRED_VALUE_NULL_MAX_RATIO,
    REQUIRED_VALUE_UNIQUE_IDENTIFIER_NAME_TOKENS,
)
from .free_text import looks_free_text_column
from .context import ColumnRuleContext
from .helpers import (
    duplicate_value_row_indexes,
    is_likely_required,
    looks_address_column,
    matching_row_indexes,
    truncated_address_row_indexes,
)
from ..shared.findings import build_finding
from ..shared.text_checks import contains_broken_text, has_special_char_issue, has_whitespace_issue

SEJONG_SIDO_VALUES = {"세종특별자치시", "세종시"}


def _normalize_name_for_identifier_check(value: str) -> str:
    return value.replace(" ", "").replace("_", "").replace("-", "").upper()


def _normalize_column_name(value: str) -> str:
    return value.replace(" ", "").replace("_", "").replace("-", "")


def _looks_unique_identifier_column(context: ColumnRuleContext) -> bool:
    column = context.column
    name = _normalize_name_for_identifier_check(f"{column.raw_name}{column.normalized_name}")
    if not any(token.upper() in name for token in REQUIRED_VALUE_UNIQUE_IDENTIFIER_NAME_TOKENS):
        return False
    if any(token.upper() in name for token in REQUIRED_VALUE_NON_UNIQUE_NAME_TOKENS):
        return False
    if column.non_empty_count <= 1 or column.distinct_count is None:
        return False
    distinct_ratio = column.distinct_count / column.non_empty_count
    return distinct_ratio >= 0.8


def _looks_sigungu_column(context: ColumnRuleContext) -> bool:
    name = _normalize_column_name(f"{context.column.raw_name}{context.column.normalized_name}")
    return "시군구" in name


def _find_sido_column_name(context: ColumnRuleContext) -> str | None:
    if not context.rows:
        return None

    current_name = context.column.raw_name
    fallback_matches: list[str] = []
    for name in context.rows[0].keys():
        if name == current_name:
            continue
        normalized_name = _normalize_column_name(name)
        if normalized_name == "시도명":
            return name
        if normalized_name in {"시도", "광역시도", "광역시도명"} or "시도" in normalized_name:
            fallback_matches.append(name)
    return fallback_matches[0] if fallback_matches else None


def _optional_sigungu_row_indexes(context: ColumnRuleContext) -> set[int]:
    if not _looks_sigungu_column(context):
        return set()

    sido_column_name = _find_sido_column_name(context)
    if not sido_column_name:
        return set()

    optional_rows: set[int] = set()
    for row_index, row in enumerate(context.rows, start=1):
        if (row.get(sido_column_name) or "").strip() in SEJONG_SIDO_VALUES:
            optional_rows.add(row_index)
    return optional_rows


def find_garbled_text(context: ColumnRuleContext) -> list[ValidationFinding]:
    column = context.column
    if not (
        contains_broken_text(column.raw_name)
        or any(contains_broken_text(value) for value in column.sample_values)
    ):
        return []

    return [
        build_finding(
            column_name=column.raw_name,
            severity="error",
            category_group="completeness",
            criterion_name="garbled_text",
            message="컬럼명 또는 샘플 데이터에 글자 깨짐이 의심됩니다.",
            row_indexes=matching_row_indexes(context.rows, column.raw_name, contains_broken_text),
            evidence=column.sample_values[:3],
        )
    ]


def find_whitespace_issues(context: ColumnRuleContext) -> list[ValidationFinding]:
    column = context.column
    has_value_issue = any(has_whitespace_issue(value) for value in context.sample_values)
    if not (has_whitespace_issue(column.raw_name) or has_value_issue):
        return []

    return [
        build_finding(
            column_name=column.raw_name,
            severity="warning",
            category_group="completeness",
            criterion_name="whitespace_special_characters",
            rule_id="whitespace_issue",
            message="컬럼명 또는 값에 앞뒤 공백이나 연속 공백이 포함된 것으로 보입니다.",
            row_indexes=matching_row_indexes(
                context.rows,
                column.raw_name,
                has_whitespace_issue,
                strip_value=False,
            ),
            evidence=[value for value in context.sample_values if has_whitespace_issue(value)][:3],
        )
    ]


def find_special_character_issues(context: ColumnRuleContext) -> list[ValidationFinding]:
    column = context.column
    has_value_issue = any(has_special_char_issue(value) for value in context.sample_values)
    if not (has_special_char_issue(column.raw_name) or has_value_issue):
        return []

    return [
        build_finding(
            column_name=column.raw_name,
            severity="warning",
            category_group="completeness",
            criterion_name="whitespace_special_characters",
            rule_id="special_character_issue",
            message=(
                "컬럼명 또는 값에 허용 범위를 벗어난 특수문자가 포함된 것으로 보입니다."
            ),
            row_indexes=matching_row_indexes(
                context.rows,
                column.raw_name,
                has_special_char_issue,
                strip_value=False,
            ),
            evidence=[value for value in context.sample_values if has_special_char_issue(value)][:3],
        )
    ]


def find_truncated_address(context: ColumnRuleContext) -> list[ValidationFinding]:
    column = context.column
    if not looks_address_column(column):
        return []

    row_indexes = truncated_address_row_indexes(context.rows, column.raw_name)
    if not row_indexes:
        return []

    return [
        build_finding(
            column_name=column.raw_name,
            severity="warning",
            category_group="domain_validity",
            criterion_name="categorical_semantic_domain",
            rule_id="categorical_value_truncated",
            message=(
                "주소 값의 괄호 또는 시설명 부분이 닫히지 않아 입력 중 잘렸거나 "
                "불완전한 주소일 수 있습니다."
            ),
            row_indexes=row_indexes,
            related_columns=[column.raw_name],
            evidence=[
                f"truncated_address_rows:{len(row_indexes)}",
                "detector:truncated_address",
            ],
        )
    ]


def find_missing_assigned_rules(context: ColumnRuleContext) -> list[ValidationFinding]:
    column = context.column
    if column.assigned_rules:
        return []
    if looks_free_text_column(column):
        return []

    return [
        build_finding(
            column_name=column.raw_name,
            severity="warning",
            category_group="completeness",
            criterion_name="required_value",
            message="검증 규칙이 할당되지 않아 수동 검토가 필요합니다.",
            rule_id="manual_review_required",
        )
    ]


def find_required_nulls(context: ColumnRuleContext) -> list[ValidationFinding]:
    column = context.column
    if not (is_likely_required(column) and (column.null_count or 0) > 0):
        return []

    optional_row_indexes = _optional_sigungu_row_indexes(context)
    null_row_indexes = [
        row_index
        for row_index in matching_row_indexes(
            context.rows,
            column.raw_name,
            lambda value: not value.strip(),
        )
        if row_index not in optional_row_indexes
    ]
    if not null_row_indexes:
        return []

    applicable_row_count = len(context.rows) - len(optional_row_indexes) if context.rows else None
    effective_null_ratio = (
        round(len(null_row_indexes) / applicable_row_count, 4)
        if applicable_row_count and applicable_row_count > 0
        else column.null_ratio
    )
    if effective_null_ratio is not None and effective_null_ratio > REQUIRED_VALUE_NULL_MAX_RATIO:
        return []

    evidence = []
    if effective_null_ratio is not None:
        evidence.append(f"null_ratio:{effective_null_ratio}")
    if optional_row_indexes:
        evidence.append("conditional_optional:sejong_sigungu")

    return [
        build_finding(
            column_name=column.raw_name,
            severity="warning",
            category_group="completeness",
            criterion_name="required_value",
            message=(
                f"필수성이 높은 컬럼으로 추정되나 결측값 {len(null_row_indexes)}건이 존재합니다."
            ),
            row_indexes=null_row_indexes,
            evidence=evidence,
        )
    ]


def find_duplicate_identifiers(context: ColumnRuleContext) -> list[ValidationFinding]:
    column = context.column
    if not (
        ("identifier" in column.semantic_tags or "duplicate_data" in column.assigned_rules)
        and _looks_unique_identifier_column(context)
        and column.distinct_count is not None
        and column.non_empty_count > column.distinct_count
    ):
        return []

    return [
        build_finding(
            column_name=column.raw_name,
            severity="warning",
            category_group="completeness",
            criterion_name="duplicate_data",
            message="식별자 성격의 컬럼에서 중복 데이터가 탐지되었습니다.",
            row_indexes=duplicate_value_row_indexes(context.rows, column.raw_name),
            evidence=[f"non_empty:{column.non_empty_count}", f"distinct:{column.distinct_count}"],
        )
    ]
