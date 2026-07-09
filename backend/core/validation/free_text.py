from __future__ import annotations

import re

from ..config.constants import FREE_TEXT_COLUMN_NAME_TOKENS
from ..schema.models import ColumnProfile

FREE_FORMAT = "free_format"
FIXED_FORMAT = "fixed_format"


def _compact_name(value: str) -> str:
    return re.sub(r"[\s_\-./()]+", "", value or "").lower()


def looks_free_text_column(column: ColumnProfile) -> bool:
    name = f"{column.raw_name} {column.normalized_name}"
    compact_name = _compact_name(name)

    if "free_text" in column.semantic_tags:
        return True

    structured_tags = {
        "address",
        "date",
        "phone",
        "numeric",
        "count",
        "quantity",
        "amount",
        "rate",
        "width",
        "identifier",
        "code",
        "boolean",
        "name",
        "geo_lat",
        "geo_lon",
        "coordinate_pair",
    }
    if structured_tags.intersection(set(column.semantic_tags)):
        return False
    structured_name_tokens = (
        "주소",
        "소재지",
        "일자",
        "일시",
        "날짜",
        "년월",
        "전화",
        "연락처",
        "번호",
        "코드",
        "구분",
        "유형",
        "상태",
        "여부",
        "유무",
        "기관명",
        "시설명",
        "자원명",
        "학교명",
        "업소명",
        "서비스명",
        "프로그램명",
        "사업명",
        "명칭",
        "위도",
        "경도",
    )
    if any(token in name for token in structured_name_tokens):
        return False

    for token in FREE_TEXT_COLUMN_NAME_TOKENS:
        normalized_token = _compact_name(token)
        if token in name or (normalized_token and normalized_token in compact_name):
            return True

    if column.inferred_primitive_type != "string":
        return False
    long_samples = [value.strip() for value in column.sample_values if len(value.strip()) >= 12]
    return len(long_samples) >= 2


def column_format_kind(column: ColumnProfile) -> str:
    return FREE_FORMAT if looks_free_text_column(column) else FIXED_FORMAT


def is_free_format_column(column: ColumnProfile) -> bool:
    return column.format_kind == FREE_FORMAT or looks_free_text_column(column)
