from __future__ import annotations

from typing import Any

from backend.config.validation import TAG_RULE_MAP, VALIDATION_CRITERIA
from backend.domain.entities.models import ColumnProfile
from backend.domain.policies.free_text import column_format_kind, looks_free_text_column

from .confidence import coerce_resolution_confidence

NON_UNIQUE_NAME_TOKENS = (
    "명",
    "명칭",
    "이름",
    "기관",
    "부서",
    "담당",
    "경찰서",
    "시설",
    "업소",
    "주소",
    "소재지",
)
ROUTING_TAG_TOKENS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("date", ("일자", "일시", "날짜", "년월", "등록일", "기준일")),
    ("address", ("주소", "소재지")),
    ("geo_lat", ("위도",)),
    ("geo_lon", ("경도",)),
    ("boolean", ("여부", "유무", "YN", "Yn", "yn", "Y/N")),
    ("enum", ("구분", "유형", "종류", "상태", "분류")),
    ("code", ("코드",)),
    ("name", ("명", "명칭", "이름", "기관명", "시설명", "경찰서명")),
    ("quantity", ("대수", "개수", "건수", "수량", "좌석수", "정원수")),
    ("width", ("폭", "너비")),
    ("phone", ("전화", "연락처", "휴대전화")),
)
NON_UNIQUE_NAME_EXCLUDED_RULES = {"duplicate_data", "number_domain"}

__all__ = [
    "allowed_rule_ids",
    "apply_llm_route",
    "apply_rule_fallback",
    "build_rule_tags",
    "looks_non_unique_name_column",
    "routing_confidence",
    "string_list",
]


def _unique_strings(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def build_rule_tags(column: ColumnProfile) -> list[str]:
    if looks_free_text_column(column):
        return ["free_text"]

    tags = set(column.semantic_tags)
    name = f"{column.raw_name} {column.normalized_name}"
    for tag, tokens in ROUTING_TAG_TOKENS:
        if any(token in name for token in tokens):
            tags.add(tag)
    return sorted(tags)


def allowed_rule_ids() -> set[str]:
    return {
        rule_id
        for category in VALIDATION_CRITERIA.values()
        for rule_id in category["criteria"].keys()
    }


def string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def looks_non_unique_name_column(column: ColumnProfile) -> bool:
    name = f"{column.raw_name} {column.normalized_name}"
    return any(token in name for token in NON_UNIQUE_NAME_TOKENS)


def routing_confidence(value: Any) -> float:
    return coerce_resolution_confidence(value)


def apply_rule_fallback(column: ColumnProfile) -> ColumnProfile:
    rule_ids: list[str] = []
    rule_tags = build_rule_tags(column)
    if rule_tags:
        column.semantic_tags = _unique_strings(rule_tags)
    for tag in rule_tags:
        rule_ids.extend(TAG_RULE_MAP.get(tag, []))
    column.assigned_rules = _unique_strings(rule_ids)
    column.format_kind = column_format_kind(column)
    return column


def apply_llm_route(column: ColumnProfile, payload: dict[str, Any]) -> ColumnProfile:
    resolved_rule_ids = allowed_rule_ids()
    is_non_unique_name = looks_non_unique_name_column(column)

    normalized_name = payload.get("normalized_name")
    if isinstance(normalized_name, str) and normalized_name.strip():
        column.normalized_name = normalized_name.strip()

    semantic_tags = [
        tag for tag in string_list(payload.get("semantic_tags"))
        if tag in TAG_RULE_MAP
    ]
    if is_non_unique_name:
        semantic_tags = [tag for tag in semantic_tags if tag != "identifier"]
        if "name" not in semantic_tags:
            semantic_tags.append("name")
    if semantic_tags:
        column.semantic_tags = _unique_strings(semantic_tags)

    assigned_rules = [
        rule_id for rule_id in string_list(payload.get("assigned_rules"))
        if rule_id in resolved_rule_ids
    ]
    if looks_free_text_column(column):
        column.semantic_tags = ["free_text"]
        column.assigned_rules = []
        column.format_kind = "free_format"
        column.routing_confidence = max(column.routing_confidence, routing_confidence(payload.get("confidence")))
        return column

    if is_non_unique_name:
        assigned_rules = [
            rule_id
            for rule_id in assigned_rules
            if rule_id not in NON_UNIQUE_NAME_EXCLUDED_RULES
        ]
    if not assigned_rules and column.semantic_tags:
        for tag in column.semantic_tags:
            assigned_rules.extend(TAG_RULE_MAP.get(tag, []))
    column.assigned_rules = _unique_strings(assigned_rules)
    column.format_kind = column_format_kind(column)
    column.routing_confidence = max(column.routing_confidence, routing_confidence(payload.get("confidence")))
    return column
