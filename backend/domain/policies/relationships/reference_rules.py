from __future__ import annotations

import re
from typing import Any

from backend.domain.entities.models import ColumnProfile, ValidationFinding
from ..shared.findings import build_finding
from ..shared.settings import REFERENCE_PAIR_TOKENS
from .common import candidate_pairs, find_matching_columns, is_non_unique_local_admin_reference_pair

WHITESPACE_RE = re.compile(r"\s+")


def _looks_like_reference_key(column: ColumnProfile) -> bool:
    if {"code", "identifier"}.intersection(column.semantic_tags):
        return True

    text = " ".join(
        [
            column.raw_name,
            column.normalized_name,
        ]
    ).lower()
    return any(
        token in text
        for token in (
            "코드",
            "아이디",
            "id",
            "고유번호",
            "식별번호",
            "일련번호",
            "관리번호",
        )
    )


def _normalize_reference_code_value(value: str) -> str:
    return WHITESPACE_RE.sub("", value.strip())


def _normalize_reference_name_value(value: str) -> str:
    return WHITESPACE_RE.sub("", value.strip()).casefold()


def validate_reference_relationships(
    columns: list[ColumnProfile],
    rows: list[dict[str, str]],
    relationship_candidates: list[dict[str, Any]] | None = None,
) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    selected_pairs = candidate_pairs(
        relationship_candidates,
        {"reference_relation"},
        columns,
        exact_group_size=2,
    )
    if relationship_candidates is not None:
        pairs = selected_pairs
    else:
        pairs = [
            pair
            for code_token, name_token in REFERENCE_PAIR_TOKENS
            for pair in find_matching_columns(columns, code_token, name_token)
        ]
    for code_col, name_col in pairs:
        if is_non_unique_local_admin_reference_pair(code_col, name_col):
            continue
        if not _looks_like_reference_key(code_col):
            continue

        mapping: dict[str, set[str]] = {}
        display_codes: dict[str, str] = {}
        display_names: dict[str, dict[str, str]] = {}
        ambiguous_row_indexes: list[int] = []
        for row_index, row in enumerate(rows, start=1):
            raw_code_value = row.get(code_col.raw_name, "").strip()
            raw_name_value = row.get(name_col.raw_name, "").strip()
            code_value = _normalize_reference_code_value(raw_code_value)
            name_value = _normalize_reference_name_value(raw_name_value)
            if not code_value or not name_value:
                continue
            display_codes.setdefault(code_value, raw_code_value)
            display_names.setdefault(code_value, {}).setdefault(name_value, raw_name_value)
            mapping.setdefault(code_value, set()).add(name_value)
        ambiguous = {code: names for code, names in mapping.items() if len(names) > 1}
        if ambiguous:
            sample_code, sample_names = next(iter(ambiguous.items()))
            for row_index, row in enumerate(rows, start=1):
                if _normalize_reference_code_value(row.get(code_col.raw_name, "")) == sample_code:
                    ambiguous_row_indexes.append(row_index)
            raw_sample_names = [
                display_names[sample_code].get(name, name)
                for name in sorted(sample_names)
            ]
            findings.append(
                build_finding(
                    column_name=code_col.raw_name,
                    severity="warning",
                    category_group="relation_consistency",
                    criterion_name="reference_relation",
                    message=(
                        f"참조 관계가 불안정합니다. 동일한 '{code_col.raw_name}' 값이 "
                        f"여러 '{name_col.raw_name}' 값과 연결됩니다."
                    ),
                    row_indexes=ambiguous_row_indexes,
                    related_columns=[code_col.raw_name, name_col.raw_name],
                    evidence=[f"{display_codes.get(sample_code, sample_code)}:{', '.join(raw_sample_names[:3])}"],
                )
            )
    return findings
