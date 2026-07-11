from __future__ import annotations

import re
from collections import Counter

from backend.domain.policies.free_text import is_free_format_column as _core_is_free_format_column

DATE_COLUMN_TOKENS = (
    "일자",
    "일시",
    "날짜",
    "년월",
    "연도",
    "년도",
    "등록일",
    "기준일",
    "개방일",
    "운영일",
    "시행일",
    "공개일",
    "마감일",
    "시작일",
    "종료일",
    "접수일",
    "처리일",
    "발생일",
    "생성일",
    "수정일",
    "갱신일",
)
TIME_ONLY_COLUMN_TOKENS = ("시간", "시각")


def looks_route_name_column(column) -> bool:
    name = f"{column.raw_name} {column.normalized_name}"
    return any(
        token in name
        for token in ("도로(노선)명", "노선명", "도로명", "도로노선명")
    )


def looks_address_text_column(column) -> bool:
    name = f"{column.raw_name} {column.normalized_name}"
    return "address" in column.semantic_tags or any(token in name for token in ("주소", "소재지"))


def looks_institution_category_column(column) -> bool:
    name = f"{column.raw_name} {column.normalized_name}"
    return any(
        token in name
        for token in ("시설구분", "기관구분", "시설유형", "기관유형", "분류", "구분", "유형")
    )


def _looks_institution_classification_column(column) -> bool:
    name = f"{column.raw_name} {column.normalized_name}"
    institution_context = any(
        token in name
        for token in ("기관", "시설", "학교", "유치원", "어린이집", "보육", "교육", "수요처")
    )
    classification_context = any(
        token in name
        for token in ("구분", "유형", "분류", "종류", "급", "단계", "대상")
    )
    return institution_context and classification_context


def looks_name_column(column) -> bool:
    name = f"{column.raw_name} {column.normalized_name}"
    if any(token in name for token in ("구분명", "유형명", "상태명", "분류명", "코드명")):
        return False
    return "name" in column.semantic_tags or any(
        token in name for token in ("기관명", "자원명", "시설명", "학교명", "업소명", "명칭")
    )


def looks_business_name_column(column) -> bool:
    name = f"{column.raw_name} {column.normalized_name}"
    return any(
        token in name
        for token in (
            "업소명",
            "상호",
            "상호명",
            "업체명",
            "사업장명",
            "가맹점명",
            "매장명",
            "상점명",
            "음식점명",
            "식당명",
        )
    )


def looks_free_text_column(column) -> bool:
    return _core_is_free_format_column(column)


def _is_text_like_column(column) -> bool:
    excluded_tags = {
        "numeric",
        "count",
        "quantity",
        "amount",
        "rate",
        "width",
        "identifier",
        "date",
        "phone",
        "geo_lat",
        "geo_lon",
        "coordinate_pair",
    }
    if excluded_tags.intersection(set(column.semantic_tags)):
        return False
    return column.inferred_primitive_type not in {"numeric", "date", "empty"}


def _compact_value_set(counter: Counter[str]) -> bool:
    total = sum(counter.values())
    if total < 10 or not counter:
        return False
    distinct = len(counter)
    top_count = counter.most_common(1)[0][1]
    distinct_ratio = distinct / max(1, total)
    top_ratio = top_count / max(1, total)
    return distinct <= 80 and distinct_ratio <= 0.1 and top_ratio >= 0.2


def allows_compact_domain_variant_detection(column, counter: Counter[str]) -> bool:
    if not _is_text_like_column(column):
        return False
    if looks_route_name_column(column):
        return False
    return _compact_value_set(counter)


def allows_context_free_replacement_detection(column, counter: Counter[str]) -> bool:
    if not _is_text_like_column(column):
        return False
    if looks_free_text_column(column):
        return False
    if looks_route_name_column(column):
        return False
    structured_tags = {"enum", "code", "boolean", "name", "address"}
    if structured_tags.intersection(set(column.semantic_tags)):
        return True
    name = f"{column.raw_name} {column.normalized_name}"
    structured_tokens = (
        "명",
        "명칭",
        "주소",
        "위치",
        "구분",
        "유형",
        "종류",
        "상태",
        "정책",
        "분류",
        "도메인",
        "값",
    )
    return _compact_value_set(counter) or any(token in name for token in structured_tokens)


def allows_institution_suffix_truncation(column) -> bool:
    name = f"{column.raw_name} {column.normalized_name}"
    excluded_tags = {
        "numeric",
        "count",
        "quantity",
        "amount",
        "rate",
        "width",
        "identifier",
        "code",
        "date",
        "boolean",
        "phone",
        "geo_lat",
        "geo_lon",
        "coordinate_pair",
    }
    if excluded_tags.intersection(set(column.semantic_tags)):
        return False
    if column.inferred_primitive_type in {"numeric", "date", "empty"}:
        return False
    if looks_free_text_column(column):
        return False
    if looks_address_text_column(column):
        return False
    if looks_business_name_column(column):
        return False
    if looks_route_name_column(column):
        return False
    if any(
        token in name
        for token in ("우편번호", "우편", "번호", "코드", "일자", "일시", "날짜", "수용인원")
    ):
        return False
    return (
        "name" in column.semantic_tags
        or looks_name_column(column)
        or _looks_institution_classification_column(column)
    )


def is_public_private_category_value(value: str) -> bool:
    text = re.sub(r"\s+", "", str(value or "").strip())
    return bool(re.fullmatch(r"(공공|민간)(기관|시설)?", text))


def looks_date_column(column) -> bool:
    name = f"{column.raw_name} {column.normalized_name}"
    if any(token in name for token in TIME_ONLY_COLUMN_TOKENS) and not any(
        token in name for token in DATE_COLUMN_TOKENS
    ):
        return False
    return "date" in column.semantic_tags or any(
        token in name for token in DATE_COLUMN_TOKENS
    )


def looks_boolean_column(column) -> bool:
    name = f"{column.raw_name} {column.normalized_name}"
    return "boolean" in column.semantic_tags or any(
        token in name for token in ("여부", "유무", "YN", "Yn", "yn", "Y/N")
    )


def looks_date_value(value: str) -> bool:
    text = value.strip()
    return bool(
        re.match(r"^\d{4}(?:\.0+|년)?$", text)
        or re.match(r"^\d{4}[-./]?\d{1,2}(?:월)?$", text)
        or re.match(r"^\d{4}[-./]?\d{1,2}[-./]?\d{1,2}(?:일)?$", text)
    )


def is_yn_value(value: str) -> bool:
    return value.strip().upper() in {"Y", "N"}


def allows_local_prefix_truncation(column) -> bool:
    name = f"{column.raw_name} {column.normalized_name}"
    excluded_tags = {
        "numeric",
        "count",
        "quantity",
        "amount",
        "rate",
        "width",
        "identifier",
        "code",
        "date",
        "boolean",
        "phone",
        "geo_lat",
        "geo_lon",
        "coordinate_pair",
    }
    if excluded_tags.intersection(set(column.semantic_tags)):
        return False
    if column.inferred_primitive_type in {"numeric", "date", "empty"}:
        return False
    if looks_free_text_column(column):
        return False
    if looks_address_text_column(column):
        return False
    if looks_business_name_column(column):
        return False
    if looks_route_name_column(column):
        return False
    if any(
        token in name
        for token in ("우편번호", "우편", "번호", "코드", "일자", "일시", "날짜", "수용인원")
    ):
        return False
    return "name" in column.semantic_tags or any(
        token in name for token in ("명", "명칭", "내용", "설명", "사유", "비고", "메모")
    )


def allows_local_surface_normalization(column) -> bool:
    name = f"{column.raw_name} {column.normalized_name}"
    excluded_tags = {
        "numeric",
        "count",
        "quantity",
        "amount",
        "rate",
        "width",
        "date",
        "boolean",
        "phone",
        "geo_lat",
        "geo_lon",
        "coordinate_pair",
    }
    if excluded_tags.intersection(set(column.semantic_tags)):
        return False
    if column.inferred_primitive_type in {"numeric", "date", "empty"}:
        return False
    if looks_free_text_column(column):
        return False
    if looks_route_name_column(column):
        return False
    if any(token in name for token in ("우편번호", "우편", "일자", "일시", "날짜", "수용인원")):
        return False
    return True
