from __future__ import annotations

from typing import Any

from backend.config.llm import (
    LLM_PROMPT_SAMPLE_VALUES_LIMIT,
    LLM_PROMPT_TOP_VALUES_LIMIT,
    LLM_PROMPT_VALUE_LENGTH_LIMIT,
)
from backend.domain.entities.models import ColumnProfile


def compact_text(value: Any, *, limit: int = LLM_PROMPT_VALUE_LENGTH_LIMIT) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def compact_sample_values(values: list[Any]) -> list[str]:
    compacted = [compact_text(value) for value in values if str(value or "").strip()]
    return list(dict.fromkeys(compacted))[:LLM_PROMPT_SAMPLE_VALUES_LIMIT]


def compact_top_values(values: list[tuple[str, int]]) -> list[dict[str, Any]]:
    compacted: list[dict[str, Any]] = []
    seen: set[str] = set()
    for value, count in values:
        text = compact_text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        compacted.append({"value": text, "count": count})
        if len(compacted) >= LLM_PROMPT_TOP_VALUES_LIMIT:
            break
    return compacted


def compact_column_payload(
    column: ColumnProfile,
    *,
    include_routing_fields: bool = False,
    include_semantic_fields: bool = False,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "raw_name": column.raw_name,
        "normalized_name": column.normalized_name,
        "inferred_type": column.inferred_primitive_type,
        "sample_values": compact_sample_values(column.sample_values),
        "top_values": compact_top_values(column.top_values),
    }
    if include_routing_fields:
        payload["source"] = column.source
    if include_semantic_fields:
        payload["semantic_tags"] = column.semantic_tags
        payload["assigned_rules"] = column.assigned_rules
    return payload
