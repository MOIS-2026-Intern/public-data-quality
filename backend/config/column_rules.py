from __future__ import annotations

from backend.domain.policies.shared.settings import (
    COMPLETE_DETAIL_ADDRESS_PATTERNS,
    COMPLETE_DETAIL_ADDRESS_VALUES,
    DATE_COLUMN_NAME_TOKENS,
    DETAIL_ADDRESS_PLACEHOLDER_VALUES,
    FREE_TEXT_LONG_SAMPLE_MIN_COUNT,
    FREE_TEXT_LONG_SAMPLE_MIN_LENGTH,
    FREE_TEXT_STRUCTURED_NAME_TOKENS,
    FREE_TEXT_STRUCTURED_TAGS,
    REQUIRED_VALUE_NAME_HINT_TOKENS,
    REQUIRED_VALUE_NON_UNIQUE_NAME_TOKENS,
    REQUIRED_VALUE_NULL_MAX_RATIO,
    REQUIRED_VALUE_OPTIONAL_NAME_TOKENS,
    REQUIRED_VALUE_TAGS,
    REQUIRED_VALUE_UNIQUE_IDENTIFIER_NAME_TOKENS,
    TIME_ONLY_COLUMN_NAME_TOKENS,
)

ROUTING_NON_UNIQUE_NAME_TOKENS = (
    "명",
    "명칭",
    "이름",
    "기관",
    "부서",
    "담당",
    "경찰서",
    "시설",
    "업소",
    "주소",
    "소재지",
)
ROUTING_TAG_TOKENS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("date", ("일자", "일시", "날짜", "년월", "등록일", "기준일")),
    ("address", ("주소", "소재지")),
    ("geo_lat", ("위도",)),
    ("geo_lon", ("경도",)),
    ("boolean", ("여부", "유무", "YN", "Yn", "yn", "Y/N")),
    ("enum", ("구분", "유형", "종류", "상태", "분류")),
    ("code", ("코드",)),
    ("name", ("명", "명칭", "이름", "기관명", "시설명", "경찰서명")),
    ("quantity", ("대수", "개수", "건수", "수량", "좌석수", "정원수")),
    ("width", ("폭", "너비")),
    ("phone", ("전화", "연락처", "휴대전화")),
)
ROUTING_NON_UNIQUE_NAME_EXCLUDED_RULES = {"duplicate_data", "number_domain"}
