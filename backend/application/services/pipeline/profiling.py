from __future__ import annotations

import math
import re
from collections import Counter

from backend.application.ports import DatasetGatewayPort
from backend.config.constants import (
    PROFILE_DISTINCT_TRACK_LIMIT,
    PROFILE_SAMPLE_ROW_LIMIT,
    PROFILE_SAMPLE_VALUES_LIMIT,
    PROFILE_TOP_VALUE_LIMIT,
    PROFILE_TYPE_INFERENCE_THRESHOLD,
)
from backend.application.dto.pipeline import AgentTrace, PipelineState
from backend.domain.entities.models import ColumnProfile
from backend.domain.services.normalization import normalize_column_name, tokenize_korean_label
from backend.domain.policies.helpers import parse_datetime
from .tracing import pipeline_trace

PROFILE_STEP_NAME = "profiler"
ProfileStats = dict[str, dict]
KOREAN_RE = re.compile(r"[가-힣]")
CODE_LIKE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$|^[A-Z0-9_-]+$")
LABEL_TOKEN_RE = re.compile(
    r"(코드|번호|일련|관리|주소|상세|명칭|이름|시설|수용|인원|면적|구분|여부|일자|"
    r"날짜|전화|위도|경도|좌표|지역|행정|법정|건물|도로명|지번|유형|상태|내용|설명)$"
)


def profile_values(
    state: PipelineState,
    *,
    dataset_gateway: DatasetGatewayPort | None = None,
) -> PipelineState:
    uploaded_path = state.get("uploaded_dataset_path")
    traces = list(state.get("agent_traces", []))
    if not uploaded_path:
        traces.append(
            pipeline_trace(
                PROFILE_STEP_NAME,
                action="profile_values",
                detail="skipped:no_uploaded_dataset",
            )
        )
        return {"columns": state["columns"], "agent_traces": traces}

    columns_by_name = {column.raw_name: column for column in state["columns"]}
    preview_rows: list[dict[str, str]] = []
    validation_rows: list[dict[str, str]] = []
    stats = _initial_profile_stats(columns_by_name)

    if dataset_gateway is None:
        raise ValueError("dataset_gateway is required to profile uploaded rows.")

    uploaded_rows = [
        {key: (value or "") for key, value in row.items()}
        for row in dataset_gateway.iter_uploaded_rows(uploaded_path)
    ]
    metadata_row = _column_metadata_row(columns_by_name, uploaded_rows)
    if metadata_row:
        _apply_column_metadata(columns_by_name, metadata_row)
        traces.append(
            pipeline_trace(
                PROFILE_STEP_NAME,
                action="detect_column_metadata_row",
                detail="row=2; skipped_from_validation=true",
            )
        )
        uploaded_rows = uploaded_rows[1:]

    for row in uploaded_rows:
        normalized_row = {key: (value or "") for key, value in row.items()}
        validation_rows.append(normalized_row)
        if len(preview_rows) < PROFILE_SAMPLE_ROW_LIMIT:
            preview_rows.append(normalized_row)
        _update_profile_stats(row, columns_by_name, stats)

    updated = _apply_profile_stats(columns_by_name, stats, traces)
    dataset_meta = state["dataset_meta"]
    if updated:
        dataset_meta.total_rows = stats[updated[0].raw_name]["rows"]

    return {
        "columns": updated,
        "preview_headers": list(columns_by_name.keys()),
        "preview_rows": preview_rows,
        "validation_rows": validation_rows,
        "dataset_meta": dataset_meta,
        "agent_traces": traces,
    }


def _initial_profile_stats(columns_by_name: dict[str, ColumnProfile]) -> ProfileStats:
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


def _column_metadata_row(
    columns_by_name: dict[str, ColumnProfile],
    rows: list[dict[str, str]],
) -> dict[str, str] | None:
    if len(rows) < 2:
        return None

    headers = list(columns_by_name)
    candidate = rows[0]
    following_rows = rows[1:51]
    candidate_values = [(candidate.get(header) or "").strip() for header in headers]
    non_empty_values = [value for value in candidate_values if value]
    if len(non_empty_values) < max(2, int(len(headers) * 0.4)):
        return None

    label_like_count = sum(
        1
        for header, value in zip(headers, candidate_values, strict=False)
        if _looks_metadata_label(value, header)
    )
    label_ratio = label_like_count / max(1, len(non_empty_values))
    unique_ratio = len(set(non_empty_values)) / max(1, len(non_empty_values))
    header_code_ratio = sum(1 for header in headers if _looks_code_like(header)) / max(1, len(headers))

    comparable = 0
    different = 0
    for header, candidate_value in zip(headers, candidate_values, strict=False):
        if not candidate_value:
            continue
        following_values = [
            (row.get(header) or "").strip()
            for row in following_rows
            if (row.get(header) or "").strip()
        ][:20]
        if not following_values:
            continue
        comparable += 1
        if _metadata_value_differs_from_data(candidate_value, following_values, header):
            different += 1

    if comparable < max(2, min(5, len(non_empty_values) // 2)):
        return None

    different_ratio = different / max(1, comparable)
    if header_code_ratio >= 0.5 and label_ratio >= 0.6 and different_ratio >= 0.5:
        return {header: candidate.get(header, "") for header in headers}
    if label_ratio >= 0.7 and unique_ratio >= 0.7 and different_ratio >= 0.65:
        return {header: candidate.get(header, "") for header in headers}
    return None


def _apply_column_metadata(columns_by_name: dict[str, ColumnProfile], metadata_row: dict[str, str]) -> None:
    for raw_name, column in columns_by_name.items():
        label = (metadata_row.get(raw_name) or "").strip()
        if not _looks_metadata_label(label, raw_name):
            continue
        normalized_name, unit = normalize_column_name(label)
        column.normalized_name = normalized_name
        if unit:
            column.unit = unit
        column.tokens = tokenize_korean_label(normalized_name)
        column.standard_candidates = [label]


def _looks_metadata_label(value: str, header: str) -> bool:
    text = (value or "").strip()
    if not text or len(text) > 40:
        return False
    if text == (header or "").strip():
        return False
    if not KOREAN_RE.search(text):
        return False
    return bool(LABEL_TOKEN_RE.search(text)) or _looks_code_like(header)


def _metadata_value_differs_from_data(candidate_value: str, following_values: list[str], header: str) -> bool:
    if candidate_value in following_values:
        return False
    candidate_shape = _value_shape(candidate_value, header)
    following_shapes = [_value_shape(value, header) for value in following_values]
    if not following_shapes:
        return False
    majority_shape = Counter(following_shapes).most_common(1)[0][0]
    return candidate_shape != majority_shape and candidate_shape == "label"


def _value_shape(value: str, header: str = "") -> str:
    text = (value or "").strip()
    if not text:
        return "empty"
    if _looks_metadata_label(text, header):
        return "label"
    if re.fullmatch(r"[-+]?\d+(\.\d+)?", text.replace(",", "")):
        return "number"
    if parse_datetime(text) is not None:
        return "date"
    if _looks_code_like(text):
        return "code"
    if KOREAN_RE.search(text):
        return "korean_text"
    return "text"


def _looks_code_like(value: str) -> bool:
    text = (value or "").strip()
    return bool(text and CODE_LIKE_RE.fullmatch(text))


def _update_profile_stats(
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


def _apply_profile_stats(
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
    try:
        parsed = float(value.replace(",", ""))
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
    return parse_datetime(value) is not None
