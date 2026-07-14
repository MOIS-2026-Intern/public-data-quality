from __future__ import annotations

import math
import re
from collections import Counter

from backend.application.dto import AgentTrace
from backend.config.pipeline import PROFILE_STEP_NAME
from backend.config.profiling import (
    PROFILE_DISTINCT_TRACK_LIMIT,
    PROFILE_SAMPLE_VALUES_LIMIT,
    PROFILE_TOP_VALUE_LIMIT,
    PROFILE_TYPE_INFERENCE_THRESHOLD,
)
from backend.domain.entities.models import ColumnProfile
from backend.domain.policies.shared.parsing import parse_datetime

from .tracing import pipeline_trace

ProfileStats = dict[str, dict]
NUMERIC_CANDIDATE_RE = re.compile(r"[-+0-9.,]+$")
DATE_SEPARATED_CANDIDATE_RE = re.compile(
    r"^\d{4}(?:[-./]\d{1,2}(?:[-./]\d{1,2})?)?(?: \d{1,2}:\d{1,2}(?::\d{1,2})?)?$"
)


def initial_profile_stats(columns_by_name: dict[str, ColumnProfile]) -> ProfileStats:
    return {
        name: {
            "rows": 0,
            "null_count": 0,
            "non_empty_count": 0,
            "samples": [],
            "distinct": set(),
            "distinct_overflow": False,
            "value_counter": Counter(),
            "numeric_count": 0,
            "date_count": 0,
            "numeric_sum": 0.0,
            "numeric_min": None,
            "numeric_max": None,
        }
        for name in columns_by_name
    }


def update_profile_stats(
    row: dict[str, str],
    columns_by_name: dict[str, ColumnProfile],
    stats: ProfileStats,
) -> None:
    for name in columns_by_name:
        value = (row.get(name) or "").strip()
        bucket = stats[name]
        bucket["rows"] += 1
        if not value:
            bucket["null_count"] += 1
            continue
        bucket["non_empty_count"] += 1
        if len(bucket["samples"]) < PROFILE_SAMPLE_VALUES_LIMIT and value not in bucket["samples"]:
            bucket["samples"].append(value)
        if not bucket["distinct_overflow"]:
            bucket["distinct"].add(value)
            if len(bucket["distinct"]) > PROFILE_DISTINCT_TRACK_LIMIT:
                bucket["distinct_overflow"] = True
        bucket["value_counter"][value] += 1
        _append_numeric_value(bucket, value)
        if _is_date(value):
            bucket["date_count"] += 1


def apply_profile_stats(
    columns_by_name: dict[str, ColumnProfile],
    stats: ProfileStats,
    traces: list[AgentTrace],
) -> list[ColumnProfile]:
    updated = []
    for name, column in columns_by_name.items():
        bucket = stats[name]
        non_empty = bucket["non_empty_count"]
        rows = bucket["rows"]
        column.total_count = rows
        column.null_count = bucket["null_count"]
        column.non_empty_count = non_empty
        column.null_ratio = round(bucket["null_count"] / rows, 4) if rows else None
        column.distinct_count = None if bucket["distinct_overflow"] else len(bucket["distinct"])
        column.sample_values = bucket["samples"]
        column.top_values = bucket["value_counter"].most_common(PROFILE_TOP_VALUE_LIMIT)
        column.numeric_parse_ratio = round(bucket["numeric_count"] / non_empty, 4) if non_empty else None
        column.date_parse_ratio = round(bucket["date_count"] / non_empty, 4) if non_empty else None
        if bucket["numeric_count"]:
            column.numeric_min = bucket["numeric_min"]
            column.numeric_max = bucket["numeric_max"]
            column.numeric_mean = round(bucket["numeric_sum"] / bucket["numeric_count"], 4)
        _set_inferred_primitive_type(column, non_empty)
        updated.append(column)
        traces.append(
            pipeline_trace(
                PROFILE_STEP_NAME,
                action="profile_column",
                target=column.raw_name,
                detail=(
                    f"null_ratio={column.null_ratio}, distinct_count={column.distinct_count}, "
                    f"inferred={column.inferred_primitive_type}, top_values={column.top_values}"
                ),
            )
        )
    return updated


def _set_inferred_primitive_type(column: ColumnProfile, non_empty: int) -> None:
    if non_empty == 0:
        column.inferred_primitive_type = "empty"
    elif (column.numeric_parse_ratio or 0) >= PROFILE_TYPE_INFERENCE_THRESHOLD:
        column.inferred_primitive_type = "numeric"
    elif (column.date_parse_ratio or 0) >= PROFILE_TYPE_INFERENCE_THRESHOLD:
        column.inferred_primitive_type = "date"
    else:
        column.inferred_primitive_type = "string"


def _parse_finite_number(value: str) -> float | None:
    candidate = value.strip()
    if not candidate or not NUMERIC_CANDIDATE_RE.fullmatch(candidate):
        return None
    try:
        parsed = float(candidate.replace(",", ""))
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) else None


def _append_numeric_value(bucket: dict, value: str) -> None:
    parsed = _parse_finite_number(value)
    if parsed is None:
        return
    bucket["numeric_count"] += 1
    bucket["numeric_sum"] += parsed
    bucket["numeric_min"] = parsed if bucket["numeric_min"] is None else min(bucket["numeric_min"], parsed)
    bucket["numeric_max"] = parsed if bucket["numeric_max"] is None else max(bucket["numeric_max"], parsed)


def _is_date(value: str) -> bool:
    candidate = value.strip()
    return bool(candidate and _is_date_candidate(candidate) and parse_datetime(candidate) is not None)


def _is_date_candidate(candidate: str) -> bool:
    if candidate.isdigit():
        return len(candidate) in {4, 6, 8, 14}
    if re.fullmatch(r"\d{4}\.0+", candidate):
        return True
    if "년" in candidate:
        return bool(re.fullmatch(r"\d{4}년", candidate))
    return bool(DATE_SEPARATED_CANDIDATE_RE.fullmatch(candidate))
