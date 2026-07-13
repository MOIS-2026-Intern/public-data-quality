from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from backend.config.categorical import (
    CATEGORICAL_LLM_MAX_VALUES,
    CATEGORICAL_LLM_MIN_DISTINCT,
    CATEGORICAL_NAME_TOKENS,
    CATEGORICAL_SEMANTIC_TAGS,
)
from backend.domain.entities.models import ColumnProfile
from backend.domain.policies.categorical import looks_free_text_column

__all__ = [
    "ColumnValueIndex",
    "column_value_counter",
    "index_column_values",
    "is_candidate_column",
    "llm_skip_reason",
    "validation_values",
]


@dataclass(frozen=True)
class ColumnValueIndex:
    counter: Counter[str]
    row_indexes: dict[str, list[int]]


def is_candidate_column(column: ColumnProfile) -> bool:
    if column.distinct_count is None:
        return False
    if column.distinct_count < CATEGORICAL_LLM_MIN_DISTINCT:
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
    if distinct_count < CATEGORICAL_LLM_MIN_DISTINCT:
        return f"distinct_count={distinct_count}"
    return None


def validation_values(
    counter: Counter[str],
    *,
    limit: int = CATEGORICAL_LLM_MAX_VALUES,
) -> list[dict[str, Any]]:
    if len(counter) <= limit:
        return _value_payload(counter.most_common())

    common_limit = max(1, limit // 2)
    common_values = counter.most_common(common_limit)
    selected = list(common_values)
    selected_names = {value for value, _ in selected}
    rare_values = sorted(
        ((value, count) for value, count in counter.items() if value not in selected_names),
        key=lambda item: (item[1], item[0]),
    )
    selected.extend(rare_values[: max(0, limit - len(selected))])
    return _value_payload(selected)


def _value_payload(values: list[tuple[str, int]]) -> list[dict[str, Any]]:
    return [{"value": value, "count": count} for value, count in values]


def column_value_counter(rows: list[dict[str, str]], column_name: str) -> Counter[str]:
    return index_column_values(rows, column_name).counter


def index_column_values(rows: list[dict[str, str]], column_name: str) -> ColumnValueIndex:
    counter: Counter[str] = Counter()
    row_indexes: dict[str, list[int]] = {}
    for row_index, row in enumerate(rows, start=1):
        value = (row.get(column_name) or "").strip()
        if value:
            counter[value] += 1
            row_indexes.setdefault(value, []).append(row_index)
    return ColumnValueIndex(counter=counter, row_indexes=row_indexes)
