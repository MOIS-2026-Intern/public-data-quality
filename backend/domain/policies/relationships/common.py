from __future__ import annotations

import re
from typing import Any

from backend.domain.entities.models import ColumnProfile
from ..shared.settings import NUMERIC_PAIR_BASE_STEM_TOKENS


def _compact_name(name: str) -> str:
    return "".join(name.split())


LOCAL_ADMIN_BASE_NAMES = ("시군구", "읍면동", "법정동", "행정동")
LOCAL_ADMIN_CODE_SUFFIXES = ("", "코드", "번호", "id", "아이디", "cd")
LOCAL_ADMIN_LABEL_SUFFIXES = ("명", "이름", "명칭")
OFFICIAL_LOCAL_ADMIN_CODE_HINTS = ("행정구역코드", "표준코드", "전국코드", "전체코드")
LONG_NUMERIC_CODE_RE = re.compile(r"\d{5,}")


def base_stem(name: str) -> str:
    stem = name
    for token in NUMERIC_PAIR_BASE_STEM_TOKENS:
        stem = stem.replace(token, "")
    return stem.strip()


def is_related_numeric_pair(total_col: ColumnProfile, candidate: ColumnProfile) -> bool:
    total_stem = base_stem(total_col.normalized_name)
    candidate_stem = base_stem(candidate.normalized_name)
    if total_stem and candidate_stem and total_stem == candidate_stem:
        return True
    if total_stem and candidate_stem and (total_stem in candidate_stem or candidate_stem in total_stem):
        return True
    if total_col.unit and candidate.unit and total_col.unit == candidate.unit:
        return True
    return False


def find_matching_columns(
    columns: list[ColumnProfile],
    left_token: str,
    right_token: str,
) -> list[tuple[ColumnProfile, ColumnProfile]]:
    matches: list[tuple[ColumnProfile, ColumnProfile]] = []
    left_candidates = [column for column in columns if left_token in column.normalized_name]
    right_candidates = [column for column in columns if right_token in column.normalized_name]
    for left in left_candidates:
        stem = left.normalized_name.replace(left_token, "")
        for right in right_candidates:
            other_stem = right.normalized_name.replace(right_token, "")
            if stem and stem == other_stem:
                matches.append((left, right))
    return matches


def columns_by_name(columns: list[ColumnProfile]) -> dict[str, ColumnProfile]:
    return {column.raw_name: column for column in columns}


def _normalized_column_names(column: ColumnProfile) -> set[str]:
    return {
        _compact_name(column.raw_name).lower(),
        _compact_name(column.normalized_name).lower(),
    }


def _matches_column_name(column: ColumnProfile, expected_names: set[str]) -> bool:
    return bool(_normalized_column_names(column).intersection(expected_names))


def _matches_local_admin_variant(name: str, base: str, suffixes: tuple[str, ...]) -> bool:
    if not name.startswith(base):
        return False
    return name[len(base) :] in suffixes


def _non_empty_column_samples(column: ColumnProfile) -> list[str]:
    values = [str(value).strip() for value in column.sample_values if str(value).strip()]
    values.extend(str(value).strip() for value, _count in column.top_values if str(value).strip())
    return list(dict.fromkeys(values))


def _looks_like_nationwide_official_local_admin_code(column: ColumnProfile, base: str) -> bool:
    names = _normalized_column_names(column)
    if any(hint in name for name in names for hint in OFFICIAL_LOCAL_ADMIN_CODE_HINTS):
        return True
    if not any(_matches_local_admin_variant(name, base, ("코드",)) for name in names):
        return False

    samples = _non_empty_column_samples(column)
    return bool(samples) and all(LONG_NUMERIC_CODE_RE.fullmatch(sample) for sample in samples)


def _local_admin_role(column: ColumnProfile) -> tuple[str, str] | None:
    names = _normalized_column_names(column)
    for base in LOCAL_ADMIN_BASE_NAMES:
        if any(_matches_local_admin_variant(name, base, LOCAL_ADMIN_CODE_SUFFIXES) for name in names):
            return base, "code"
        if any(_matches_local_admin_variant(name, base, LOCAL_ADMIN_LABEL_SUFFIXES) for name in names):
            return base, "label"
    return None


def is_non_unique_local_admin_reference_pair(left: ColumnProfile, right: ColumnProfile) -> bool:
    left_role = _local_admin_role(left)
    right_role = _local_admin_role(right)
    if left_role is None or right_role is None:
        return False
    if left_role[0] != right_role[0] or left_role[1] == right_role[1]:
        return False

    code_column = left if left_role[1] == "code" else right
    return not _looks_like_nationwide_official_local_admin_code(code_column, left_role[0])


def candidate_groups(
    relationship_candidates: list[dict[str, Any]] | None,
    rule_ids: set[str],
    columns: list[ColumnProfile],
) -> list[list[ColumnProfile]]:
    if not relationship_candidates:
        return []

    by_name = columns_by_name(columns)
    groups: list[list[ColumnProfile]] = []
    for candidate in relationship_candidates:
        if candidate.get("rule_id") not in rule_ids:
            continue
        names = candidate.get("columns") or []
        if not isinstance(names, list):
            continue
        group = [by_name[name] for name in names if isinstance(name, str) and name in by_name]
        if len(group) >= 2:
            groups.append(group)
    return groups


def candidate_pairs(
    relationship_candidates: list[dict[str, Any]] | None,
    rule_ids: set[str],
    columns: list[ColumnProfile],
    *,
    exact_group_size: int | None = None,
) -> list[tuple[ColumnProfile, ColumnProfile]]:
    pairs: list[tuple[ColumnProfile, ColumnProfile]] = []
    for group in candidate_groups(relationship_candidates, rule_ids, columns):
        if exact_group_size is not None and len(group) != exact_group_size:
            continue
        pairs.append((group[0], group[1]))
    return pairs
