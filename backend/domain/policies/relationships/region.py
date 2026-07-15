from __future__ import annotations

import re

from backend.config.relationships import (
    REGION_ADDRESS_EXCLUDED_NAME_TOKENS,
    REGION_ADDRESS_NAME_TOKENS,
    REGION_COLUMN_NAME_TOKENS,
    REGION_EXACT_VALUES,
    REGION_GENERIC_VALUE_PATTERNS,
    REGION_LIKE_MIN_RATIO,
    REGION_SAMPLE_ROW_LIMIT,
)
from backend.domain.entities.models import ColumnProfile

_REGION_VALUE_PATTERN_BODY = "|".join((*REGION_EXACT_VALUES, *REGION_GENERIC_VALUE_PATTERNS))

REGION_VALUE_RE = re.compile(
    rf"^(?:{_REGION_VALUE_PATTERN_BODY})$"
)

REGION_PREFIX_RE = re.compile(
    rf"^({_REGION_VALUE_PATTERN_BODY})(?:\s|$)"
)


def looks_region_column(column: ColumnProfile, rows: list[dict[str, str]]) -> bool:
    name = f"{column.raw_name} {column.normalized_name}"
    if any(token in name for token in REGION_COLUMN_NAME_TOKENS):
        return True

    non_empty = 0
    region_like = 0
    for row in rows[:REGION_SAMPLE_ROW_LIMIT]:
        value = (row.get(column.raw_name) or "").strip()
        if not value:
            continue
        non_empty += 1
        if REGION_VALUE_RE.fullmatch(value):
            region_like += 1
    return non_empty > 0 and region_like / non_empty >= REGION_LIKE_MIN_RATIO


def looks_address_column(column: ColumnProfile) -> bool:
    name = f"{column.raw_name} {column.normalized_name}"
    return (
        "address" in column.semantic_tags
        or any(token in name for token in REGION_ADDRESS_NAME_TOKENS)
    ) and not any(token in name for token in REGION_ADDRESS_EXCLUDED_NAME_TOKENS)


def address_region_prefix(address_value: str) -> str:
    match = REGION_PREFIX_RE.match(address_value)
    return match.group(1) if match else ""
