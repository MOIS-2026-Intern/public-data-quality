from __future__ import annotations

import re
from collections import Counter

from .text import is_numeric_like_value, normalized_text

SHORT_KOREAN_PREFIX_LEN = 2
MIN_TRUNCATED_PREFIX_LEN = 3
MIN_TRUNCATED_PREFIX_RATIO = 0.25
ENTITY_COMPLETION_SUFFIXES = {
    "교",
    "원",
    "관",
    "소",
    "당",
    "집",
    "학교",
    "유치원",
    "어린이집",
    "병원",
    "의원",
    "약국",
    "학원",
    "센터",
    "회관",
    "복지관",
    "도서관",
    "보건소",
    "경로당",
    "관리소",
}
COMPLETE_LOCATION_VALUES = {
    "정문",
    "후문",
    "입구",
    "교내",
    "본관",
    "별관",
    "강당",
    "운동장",
    "주차장",
    "앞",
    "뒤",
    "뒷편",
    "뒤편",
    "서편",
    "동편",
    "남편",
    "북편",
    "지상",
    "지하",
}
FACILITY_QUALIFIER_SUFFIXES = {
    "주차장",
    "명절주차장",
    "체육관주차장",
    "운동장주차장",
    "공영주차장",
}


def is_normal_qualifier_suffix(suffix: str) -> bool:
    text = str(suffix or "").strip()
    if not text:
        return False

    normal_suffix_patterns = (
        r"^\d+호점$",
        r"^[A-Z]$",
        r"^[가-힣A-Z0-9]+점$",
        r"^분관$",
        r"^별관$",
        r"^본관$",
    )
    return any(re.fullmatch(pattern, text) for pattern in normal_suffix_patterns)


def is_complete_entity_or_location_value(value: str) -> bool:
    text = normalized_text(value)
    if not text:
        return False
    if text in COMPLETE_LOCATION_VALUES:
        return True
    return any(text.endswith(suffix) for suffix in ENTITY_COMPLETION_SUFFIXES)


def is_short_korean_entity_prefix(short_norm: str, long_norm: str) -> bool:
    if len(short_norm) != SHORT_KOREAN_PREFIX_LEN:
        return False
    if not re.fullmatch(r"[가-힣]+", short_norm):
        return False
    if not long_norm.startswith(short_norm):
        return False

    suffix = long_norm[len(short_norm) :]
    if not suffix:
        return False
    return suffix in ENTITY_COMPLETION_SUFFIXES


def find_truncated_value_pairs(counter: Counter[str]) -> list[tuple[str, str]]:
    values = [value.strip() for value in counter if value and value.strip()]
    candidate_pairs: list[tuple[str, str]] = []

    for short_value in values:
        short_norm = normalized_text(short_value)
        if len(short_norm) < SHORT_KOREAN_PREFIX_LEN:
            continue
        if is_numeric_like_value(short_norm):
            continue
        for long_value in values:
            if short_value == long_value:
                continue
            long_norm = normalized_text(long_value)
            if is_numeric_like_value(long_norm):
                continue
            if len(long_norm) < len(short_norm) + 1:
                continue
            if short_norm == long_norm:
                continue
            if len(short_norm) < MIN_TRUNCATED_PREFIX_LEN and not is_short_korean_entity_prefix(short_norm, long_norm):
                continue
            if not long_norm.startswith(short_norm):
                continue
            if len(short_norm) / max(1, len(long_norm)) < MIN_TRUNCATED_PREFIX_RATIO:
                continue
            suffix = long_norm[len(short_norm) :]
            if (
                is_complete_entity_or_location_value(short_norm)
                and suffix in FACILITY_QUALIFIER_SUFFIXES
            ):
                continue
            if short_norm in COMPLETE_LOCATION_VALUES:
                continue
            if is_normal_qualifier_suffix(suffix):
                continue
            if counter[long_value] <= counter[short_value]:
                continue
            candidate_pairs.append((short_value, long_value))

    unique_pairs = sorted(set(candidate_pairs))
    long_values_by_short: dict[str, set[str]] = {}
    short_values_by_long: dict[str, set[str]] = {}
    for short_value, long_value in unique_pairs:
        long_values_by_short.setdefault(short_value, set()).add(long_value)
        short_values_by_long.setdefault(long_value, set()).add(short_value)

    one_to_one_pairs: list[tuple[str, str]] = []
    for short_value, long_value in unique_pairs:
        if len(long_values_by_short.get(short_value, set())) != 1:
            continue
        if len(short_values_by_long.get(long_value, set())) != 1:
            continue
        one_to_one_pairs.append((short_value, long_value))
    return one_to_one_pairs
