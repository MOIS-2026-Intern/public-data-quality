from __future__ import annotations

import re

from backend.config.column_rules import (
    FREE_TEXT_LONG_SAMPLE_MIN_COUNT,
    FREE_TEXT_LONG_SAMPLE_MIN_LENGTH,
    FREE_TEXT_STRUCTURED_NAME_TOKENS,
    FREE_TEXT_STRUCTURED_TAGS,
)
from backend.config.validation import FREE_TEXT_COLUMN_NAME_TOKENS
from backend.domain.entities.models import ColumnProfile

FREE_FORMAT = "free_format"
FIXED_FORMAT = "fixed_format"


def _compact_name(value: str) -> str:
    return re.sub(r"[\s_\-./()]+", "", value or "").lower()


def looks_free_text_column(column: ColumnProfile) -> bool:
    name = f"{column.raw_name} {column.normalized_name}"
    compact_name = _compact_name(name)

    if "free_text" in column.semantic_tags:
        return True

    if FREE_TEXT_STRUCTURED_TAGS.intersection(set(column.semantic_tags)):
        return False
    if any(token in name for token in FREE_TEXT_STRUCTURED_NAME_TOKENS):
        return False

    for token in FREE_TEXT_COLUMN_NAME_TOKENS:
        normalized_token = _compact_name(token)
        if token in name or (normalized_token and normalized_token in compact_name):
            return True

    if column.inferred_primitive_type != "string":
        return False
    long_samples = [
        value.strip()
        for value in column.sample_values
        if len(value.strip()) >= FREE_TEXT_LONG_SAMPLE_MIN_LENGTH
    ]
    return len(long_samples) >= FREE_TEXT_LONG_SAMPLE_MIN_COUNT


def column_format_kind(column: ColumnProfile) -> str:
    return FREE_FORMAT if looks_free_text_column(column) else FIXED_FORMAT


def is_free_format_column(column: ColumnProfile) -> bool:
    return column.format_kind == FREE_FORMAT or looks_free_text_column(column)
