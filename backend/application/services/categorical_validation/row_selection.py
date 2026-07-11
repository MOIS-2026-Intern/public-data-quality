from __future__ import annotations

from collections import Counter
from typing import Any

from backend.config.categorical import (
    ROW_CONTEXT_CATEGORY_TOKENS,
    ROW_CONTEXT_DEFAULT_LIMIT,
    ROW_CONTEXT_EARLY_SAMPLE_LIMIT,
    ROW_CONTEXT_EARLY_SAMPLE_REASON,
    ROW_CONTEXT_MAX_COLUMNS,
    ROW_CONTEXT_ORGANIZATION_TOKENS,
    ROW_CONTEXT_PRIORITY_TAGS,
    ROW_CONTEXT_RARE_VALUE_COUNT,
    ROW_CONTEXT_REGION_TOKENS,
    ROW_CONTEXT_SIGNAL_COUNT_LIMIT,
    ROW_CONTEXT_SIGNAL_SCORES,
    ROW_CONTEXT_SIGNAL_TOKENS,
    ROW_CONTEXT_UNIQUE_VALUE_COUNT,
    ROW_CONTEXT_USEFUL_TOKENS,
)
from backend.domain.policies.categorical import looks_free_text_column


def context_columns(columns) -> list[dict[str, Any]]:
    selected = []
    for column in columns:
        if looks_free_text_column(column):
            continue
        name = f"{column.raw_name} {column.normalized_name}"
        if any(token in name for token in ROW_CONTEXT_USEFUL_TOKENS) or ROW_CONTEXT_PRIORITY_TAGS.intersection(
            column.semantic_tags
        ):
            selected.append(
                {
                    "raw_name": column.raw_name,
                    "normalized_name": column.normalized_name,
                    "semantic_tags": column.semantic_tags,
                    "semantic_profile_label": column.semantic_profile_label,
                }
            )
    return selected[:ROW_CONTEXT_MAX_COLUMNS]


def looks_row_context_signal_column(header: str) -> bool:
    return any(token in header for token in ROW_CONTEXT_SIGNAL_TOKENS)


def row_context_signal_score(header: str, count: int) -> int:
    if count > ROW_CONTEXT_SIGNAL_COUNT_LIMIT:
        return 0
    if any(token in header for token in ROW_CONTEXT_REGION_TOKENS):
        return ROW_CONTEXT_SIGNAL_SCORES["region"][count]
    if any(token in header for token in ROW_CONTEXT_ORGANIZATION_TOKENS):
        return ROW_CONTEXT_SIGNAL_SCORES["organization"][count]
    if any(token in header for token in ROW_CONTEXT_CATEGORY_TOKENS):
        return ROW_CONTEXT_SIGNAL_SCORES["category"][count]
    return ROW_CONTEXT_SIGNAL_SCORES["default"][count]


def context_rows(
    rows: list[dict[str, str]],
    headers: list[str],
    limit: int = ROW_CONTEXT_DEFAULT_LIMIT,
) -> list[dict[str, Any]]:
    value_counts: dict[str, Counter[str]] = {}
    for header in headers:
        if not looks_row_context_signal_column(header):
            continue
        counter = Counter()
        for row in rows:
            value = (row.get(header) or "").strip()
            if value:
                counter[value] += 1
        value_counts[header] = counter

    candidates: dict[int, dict[str, Any]] = {}
    for row_index, row in enumerate(rows, start=1):
        reasons: list[str] = []
        score = 0
        for header, counter in value_counts.items():
            value = (row.get(header) or "").strip()
            if not value:
                continue
            count = counter.get(value, 0)
            score += row_context_signal_score(header, count)
            if count == ROW_CONTEXT_UNIQUE_VALUE_COUNT:
                reasons.append(f"{header} has unique value '{value}'")
            elif count == ROW_CONTEXT_RARE_VALUE_COUNT:
                reasons.append(f"{header} has rare value '{value}'")
        if reasons:
            candidates[row_index] = {
                "row_index": row_index,
                "candidate_score": score,
                "candidate_reasons": reasons[:4],
                "values": {header: row.get(header, "") for header in headers},
            }

    prioritized_candidates = sorted(
        candidates.values(),
        key=lambda item: (-int(item.get("candidate_score") or 0), int(item.get("row_index") or 0)),
    )
    selected: list[dict[str, Any]] = prioritized_candidates[: max(0, limit - ROW_CONTEXT_EARLY_SAMPLE_LIMIT)]
    selected_indexes = {item["row_index"] for item in selected}
    for row_index, row in enumerate(rows[:ROW_CONTEXT_EARLY_SAMPLE_LIMIT], start=1):
        if row_index in selected_indexes:
            continue
        selected.append(
            {
                "row_index": row_index,
                "candidate_reasons": [ROW_CONTEXT_EARLY_SAMPLE_REASON],
                "values": {header: row.get(header, "") for header in headers},
            }
        )
        if len(selected) >= limit:
            break
    return selected[:limit]
