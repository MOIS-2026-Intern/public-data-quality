from __future__ import annotations

import re

from backend.config.column_rules import (
    DATE_DAY_OF_MONTH_MIN_COUNT,
    DATE_DAY_OF_MONTH_MIN_DISTINCT_DAYS,
    DATE_DAY_OF_MONTH_MIN_RATIO,
)
from backend.domain.entities.models import ValidationFinding
from ..shared.settings import (
    BOOLEAN_ALLOWED_VALUES,
    DATE_COLUMN_NAME_TOKENS,
    TIME_ONLY_COLUMN_NAME_TOKENS,
)
from .context import ColumnRuleContext
from .helpers import matching_row_indexes
from ..shared.findings import build_finding
from ..shared.parsing import parse_datetime
from ..shared.text_checks import looks_phone_number_text


def _looks_time_only_column(column) -> bool:
    name = f"{column.raw_name} {column.normalized_name}"
    return any(token in name for token in TIME_ONLY_COLUMN_NAME_TOKENS) and not any(
        token in name for token in DATE_COLUMN_NAME_TOKENS
    )


def _looks_date_domain_column(column) -> bool:
    if _looks_time_only_column(column):
        return False

    name = f"{column.raw_name} {column.normalized_name}"
    if any(token in name for token in DATE_COLUMN_NAME_TOKENS):
        return True

    return column.inferred_primitive_type == "date" or (column.date_parse_ratio or 0) > 0


def _is_day_of_month_distribution(values: list[str]) -> bool:
    non_empty_values = [str(value or "").strip() for value in values if str(value or "").strip()]
    if len(non_empty_values) < DATE_DAY_OF_MONTH_MIN_COUNT:
        return False

    day_values = [
        value
        for value in non_empty_values
        if re.fullmatch(r"\d{1,2}", value) and 1 <= int(value) <= 31
    ]
    if len(day_values) / len(non_empty_values) < DATE_DAY_OF_MONTH_MIN_RATIO:
        return False

    distinct_days = {int(value) for value in day_values}
    return len(distinct_days) >= DATE_DAY_OF_MONTH_MIN_DISTINCT_DAYS


def find_invalid_dates(context: ColumnRuleContext) -> list[ValidationFinding]:
    column = context.column
    if not (
        "date" in column.semantic_tags
        and _looks_date_domain_column(column)
        and column.date_parse_ratio is not None
        and column.date_parse_ratio < 1.0
    ):
        return []

    values = [row.get(column.raw_name, "") for row in context.rows] if context.rows else column.sample_values
    if _is_day_of_month_distribution(values):
        return []

    row_indexes = matching_row_indexes(
        context.rows,
        column.raw_name,
        lambda value: bool(value) and parse_datetime(value) is None,
    )
    if not row_indexes:
        return []

    return [
        build_finding(
            column_name=column.raw_name,
            severity="warning",
            category_group="domain_validity",
            criterion_name="date_domain",
            message=(
                "날짜 도메인 컬럼에서 유효하지 않은 날짜 형식 또는 "
                "범위 이탈 값이 존재합니다."
            ),
            row_indexes=row_indexes,
            evidence=[f"date_parse_ratio:{column.date_parse_ratio:.2f}"],
        )
    ]


def find_invalid_phone_numbers(context: ColumnRuleContext) -> list[ValidationFinding]:
    column = context.column
    if "phone" not in column.semantic_tags:
        return []

    invalid_phone = [value for value in column.sample_values if value and not looks_phone_number_text(value)]
    if not invalid_phone:
        return []

    return [
        build_finding(
            column_name=column.raw_name,
            severity="warning",
            category_group="domain_validity",
            criterion_name="number_domain",
            message="번호 도메인 컬럼에 규칙을 벗어난 값이 포함된 것으로 보입니다.",
            row_indexes=matching_row_indexes(
                context.rows,
                column.raw_name,
                lambda value: bool(value) and not looks_phone_number_text(value),
            ),
            evidence=invalid_phone[:3],
        )
    ]


def find_invalid_booleans(context: ColumnRuleContext) -> list[ValidationFinding]:
    column = context.column
    if "boolean" not in column.semantic_tags:
        return []

    invalid_boolean = [
        value
        for value, _ in column.top_values
        if value.strip().lower() not in BOOLEAN_ALLOWED_VALUES
    ]
    if not invalid_boolean:
        return []

    return [
        build_finding(
            column_name=column.raw_name,
            severity="warning",
            category_group="domain_validity",
            criterion_name="boolean_domain",
            message="여부 도메인 컬럼에 2값 범위를 벗어난 값이 존재합니다.",
            row_indexes=matching_row_indexes(
                context.rows,
                column.raw_name,
                lambda value: bool(value.strip()) and value.strip().lower() not in BOOLEAN_ALLOWED_VALUES,
            ),
            evidence=invalid_boolean[:5],
        )
    ]
