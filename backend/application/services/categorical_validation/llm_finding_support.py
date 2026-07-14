from __future__ import annotations

import re
from collections import Counter

from backend.domain.policies.categorical import value_rows


def date_format_values_to_review(
    *,
    rows: list[dict[str, str]],
    column_name: str,
    values: list[str],
    target_format: str,
) -> list[str]:
    values_by_key = {value: _date_format_key(value) for value in values}
    target_key = _normalize_date_format_key(target_format)
    if target_key and target_key in set(values_by_key.values()):
        return [value for value in values if values_by_key.get(value) != target_key]

    format_counts: Counter[str] = Counter()
    value_counts = {value: len(value_rows(rows, column_name, value)) for value in values}
    for value, format_key in values_by_key.items():
        if format_key:
            format_counts[format_key] += value_counts[value]

    if len(format_counts) <= 1:
        return values

    dominant_key, dominant_count = format_counts.most_common(1)[0]
    if sum(1 for count in format_counts.values() if count == dominant_count) > 1:
        return values

    return [value for value in values if values_by_key.get(value) and values_by_key[value] != dominant_key] or values


def invalid_format_rule_id(issue_type: str) -> str:
    if issue_type == "boolean_invalid":
        return "boolean_domain"
    if issue_type == "date_invalid":
        return "date_domain"
    if issue_type == "malformed_text":
        return "garbled_text"
    return "categorical_value_out_of_domain"


def invalid_format_criterion_name(issue_type: str) -> str:
    if issue_type == "boolean_invalid":
        return "boolean_domain"
    if issue_type == "date_invalid":
        return "date_domain"
    if issue_type == "malformed_text":
        return "garbled_text"
    return "categorical_semantic_domain"


def invalid_format_message(value: str, issue_type: str) -> str:
    if issue_type == "malformed_text":
        return f"'{value}' 값은 불필요한 기호 또는 깨진 텍스트가 포함된 것으로 보입니다."
    return f"'{value}' 값은 컬럼의 형식 또는 허용값과 맞지 않을 수 있습니다."


def _date_format_key(value: str) -> str:
    text = str(value or "").strip()
    patterns = (
        (r"^\d{4}-\d{2}-\d{2}$", "YYYY-MM-DD"),
        (r"^\d{4}-\d{1,2}-\d{1,2}$", "YYYY-M-D"),
        (r"^\d{4}\.\d{2}\.\d{2}\.?$", "YYYY.MM.DD"),
        (r"^\d{4}\.\d{1,2}\.\d{1,2}\.?$", "YYYY.M.D"),
        (r"^\d{2}\.\d{1,2}\.\d{1,2}\.?$", "YY.M.D"),
        (r"^\d{4}/\d{1,2}/\d{1,2}$", "YYYY/M/D"),
        (r"^\d{8}$", "YYYYMMDD"),
        (r"^\d{6}$", "YYMMDD"),
        (r"^\d{4}년\d{1,2}월\d{1,2}일?$", "YYYY년M월D일"),
    )
    for pattern, key in patterns:
        if re.fullmatch(pattern, text):
            return key
    return ""


def _normalize_date_format_key(value: str) -> str:
    text = re.sub(r"\s+", "", str(value or "")).upper()
    aliases = {
        "YYYY-M-D": "YYYY-M-D",
        "YYYY-MM-DD": "YYYY-MM-DD",
        "YYYY.MM.DD": "YYYY.MM.DD",
        "YYYY.M.D": "YYYY.M.D",
        "YY.M.D": "YY.M.D",
        "YYYY/MM/DD": "YYYY/M/D",
        "YYYY/M/D": "YYYY/M/D",
        "YYYYMMDD": "YYYYMMDD",
        "YYMMDD": "YYMMDD",
    }
    return aliases.get(text, text)
