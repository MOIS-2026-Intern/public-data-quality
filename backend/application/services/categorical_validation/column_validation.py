from __future__ import annotations

from collections import Counter
from typing import Any

from backend.config.categorical import (
    CATEGORICAL_LLM_MAX_DISTINCT,
    CATEGORICAL_LLM_MIN_DISTINCT,
    CATEGORICAL_NAME_TOKENS,
    CATEGORICAL_SEMANTIC_TAGS,
)
from backend.domain.entities.models import ColumnProfile
from backend.domain.policies.categorical import looks_free_text_column

__all__ = [
    "column_value_counter",
    "is_candidate_column",
    "llm_skip_reason",
    "validation_values",
]


def is_candidate_column(column: ColumnProfile) -> bool:
    if column.distinct_count is None:
        return False
    if not (CATEGORICAL_LLM_MIN_DISTINCT <= column.distinct_count <= CATEGORICAL_LLM_MAX_DISTINCT):
        return False
    if not column.top_values:
        return False
    if looks_free_text_column(column):
        return True
    return bool(CATEGORICAL_SEMANTIC_TAGS.intersection(set(column.semantic_tags))) or any(
        token in column.raw_name for token in CATEGORICAL_NAME_TOKENS
    )


def llm_skip_reason(column: ColumnProfile, counter: Counter[str]) -> str | None:
    if not is_candidate_column(column):
        return "llm_candidate_filter"
    distinct_count = len(counter)
    if distinct_count == 0:
        return "empty_counter"
    if not (CATEGORICAL_LLM_MIN_DISTINCT <= distinct_count <= CATEGORICAL_LLM_MAX_DISTINCT):
        return f"distinct_count={distinct_count}"
    return None


def validation_values(counter: Counter[str]) -> list[dict[str, Any]]:
    return [{"value": value, "count": count} for value, count in counter.most_common()]


def column_value_counter(rows: list[dict[str, str]], column_name: str) -> Counter[str]:
    counter: Counter[str] = Counter()
    for row in rows:
        value = (row.get(column_name) or "").strip()
        if value:
            counter[value] += 1
    return counter
