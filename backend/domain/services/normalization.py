from __future__ import annotations

import re

from backend.config.constants import DEFAULT_COLUMN_ROUTING_CONFIDENCE, NORMALIZATION_SYNONYM_PATCHES
from backend.domain.entities.models import ColumnProfile

PARENS_RE = re.compile(r"\(([^()]*)\)")
MULTISPACE_RE = re.compile(r"\s+")


def normalize_column_name(raw_name: str) -> tuple[str, str | None]:
    unit = None
    name = raw_name.strip()
    paren_match = PARENS_RE.search(name)
    if paren_match:
        maybe_unit = paren_match.group(1).strip()
        if maybe_unit:
            unit = maybe_unit
        name = PARENS_RE.sub("", name)

    name = MULTISPACE_RE.sub(" ", name).strip()
    name = NORMALIZATION_SYNONYM_PATCHES.get(name, name)
    return name, unit


def tokenize_korean_label(label: str) -> list[str]:
    parts = re.split(r"[\s/,_-]+", label)
    return [part for part in parts if part]


def build_column_profile(
    raw_name: str,
    source: str,
) -> ColumnProfile:
    normalized_name, unit = normalize_column_name(raw_name)
    return ColumnProfile(
        raw_name=raw_name,
        normalized_name=normalized_name,
        source=source,
        unit=unit,
        tokens=tokenize_korean_label(normalized_name),
        routing_confidence=DEFAULT_COLUMN_ROUTING_CONFIDENCE,
    )
