from __future__ import annotations

import re
from collections import Counter

from backend.config.profiling import PROFILE_UPLOADED_ROW_BUFFER_SIZE
from backend.domain.entities.models import ColumnProfile
from backend.domain.policies.shared.parsing import parse_datetime
from backend.domain.services.normalization import normalize_column_name, tokenize_korean_label

KOREAN_RE = re.compile(r"[가-힣]")
CODE_LIKE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$|^[A-Z0-9_-]+$")
LABEL_TOKEN_RE = re.compile(
    r"(코드|번호|일련|관리|주소|상세|명칭|이름|시설|수용|인원|면적|구분|여부|일자|"
    r"날짜|전화|위도|경도|좌표|지역|행정|법정|건물|도로명|지번|유형|상태|내용|설명)$"
)


def column_metadata_row(
    columns_by_name: dict[str, ColumnProfile],
    rows: list[dict[str, str]],
) -> dict[str, str] | None:
    if len(rows) < 2:
        return None

    headers = list(columns_by_name)
    candidate = rows[0]
    following_rows = rows[1:PROFILE_UPLOADED_ROW_BUFFER_SIZE]
    candidate_values = [(candidate.get(header) or "").strip() for header in headers]
    non_empty_values = [value for value in candidate_values if value]
    if len(non_empty_values) < max(2, int(len(headers) * 0.4)):
        return None

    label_like_count = sum(
        1 for header, value in zip(headers, candidate_values, strict=False) if looks_metadata_label(value, header)
    )
    label_ratio = label_like_count / max(1, len(non_empty_values))
    unique_ratio = len(set(non_empty_values)) / max(1, len(non_empty_values))
    header_code_ratio = sum(1 for header in headers if looks_code_like(header)) / max(1, len(headers))

    comparable = 0
    different = 0
    for header, candidate_value in zip(headers, candidate_values, strict=False):
        if not candidate_value:
            continue
        following_values = [(row.get(header) or "").strip() for row in following_rows if (row.get(header) or "").strip()][:20]
        if not following_values:
            continue
        comparable += 1
        if metadata_value_differs_from_data(candidate_value, following_values, header):
            different += 1

    if comparable < max(2, min(5, len(non_empty_values) // 2)):
        return None

    different_ratio = different / max(1, comparable)
    if header_code_ratio >= 0.5 and label_ratio >= 0.6 and different_ratio >= 0.5:
        return {header: candidate.get(header, "") for header in headers}
    if label_ratio >= 0.7 and unique_ratio >= 0.7 and different_ratio >= 0.65:
        return {header: candidate.get(header, "") for header in headers}
    return None


def apply_column_metadata(columns_by_name: dict[str, ColumnProfile], metadata_row: dict[str, str]) -> None:
    for raw_name, column in columns_by_name.items():
        label = (metadata_row.get(raw_name) or "").strip()
        if not looks_metadata_label(label, raw_name):
            continue
        normalized_name, unit = normalize_column_name(label)
        column.normalized_name = normalized_name
        if unit:
            column.unit = unit
        column.tokens = tokenize_korean_label(normalized_name)
        column.standard_candidates = [label]


def looks_metadata_label(value: str, header: str) -> bool:
    text = (value or "").strip()
    if not text or len(text) > 40 or text == (header or "").strip() or not KOREAN_RE.search(text):
        return False
    return bool(LABEL_TOKEN_RE.search(text)) or looks_code_like(header)


def metadata_value_differs_from_data(candidate_value: str, following_values: list[str], header: str) -> bool:
    if candidate_value in following_values:
        return False
    following_shapes = [value_shape(value, header) for value in following_values]
    if not following_shapes:
        return False
    majority_shape = Counter(following_shapes).most_common(1)[0][0]
    return value_shape(candidate_value, header) != majority_shape and value_shape(candidate_value, header) == "label"


def value_shape(value: str, header: str = "") -> str:
    text = (value or "").strip()
    if not text:
        return "empty"
    if looks_metadata_label(text, header):
        return "label"
    if re.fullmatch(r"[-+]?\d+(\.\d+)?", text.replace(",", "")):
        return "number"
    if parse_datetime(text) is not None:
        return "date"
    if looks_code_like(text):
        return "code"
    if KOREAN_RE.search(text):
        return "korean_text"
    return "text"


def looks_code_like(value: str) -> bool:
    text = (value or "").strip()
    return bool(text and CODE_LIKE_RE.fullmatch(text))
