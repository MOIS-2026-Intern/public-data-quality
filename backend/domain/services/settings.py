from __future__ import annotations

NORMALIZATION_SYNONYM_PATCHES = {
    "연락처": "전화번호",
    "데이터기준일자": "자료기준일자",
    "데이터기준일": "자료기준일자",
    "기준일자": "기준일",
    "소재지도로명주소": "도로명주소",
    "소재지지번주소": "지번주소",
    "업소명": "명칭",
    "CCTV설치여부": "설치여부",
    "CCTV설치대수": "설치대수",
}

DEFAULT_COLUMN_ROUTING_CONFIDENCE = 0.4

__all__ = [
    "DEFAULT_COLUMN_ROUTING_CONFIDENCE",
    "NORMALIZATION_SYNONYM_PATCHES",
]
