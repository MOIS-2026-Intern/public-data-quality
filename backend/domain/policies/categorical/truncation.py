from __future__ import annotations

from bisect import bisect_left
from collections import Counter
import re

from backend.config.categorical import (
    CATEGORY_QUALIFIER_SUFFIXES,
    COMPLETE_LOCATION_VALUES,
    ENTITY_COMPLETION_SUFFIXES,
    FACILITY_QUALIFIER_SUFFIXES,
    INCOMPLETE_ENTITY_MODIFIER_SUFFIXES,
    INSTITUTION_SUFFIX_COMPLETIONS,
    MIN_TRUNCATED_PREFIX_LEN,
    MIN_TRUNCATED_PREFIX_RATIO,
    NAMED_DETAIL_PREFIX_PATTERNS,
    ORGANIZATION_BRANCH_SUFFIX_PATTERNS,
    SHORT_KOREAN_PREFIX_LEN,
    STRUCTURED_DETAIL_COMPONENT_PATTERNS,
    STRUCTURED_DETAIL_EXACT_SUFFIXES_BY_LENGTH,
)
from .text import is_numeric_like_value, normalized_text


def is_normal_qualifier_suffix(suffix: str) -> bool:
    text = str(suffix or "").strip()
    if not text:
        return False
    if is_structured_location_detail_suffix(text):
        return True

    normal_suffix_patterns = (
        r"^\d+호점$",
        r"^[A-Z]$",
        r"^[가-힣A-Z0-9]+점$",
        r"^분관$",
        r"^별관$",
        r"^본관$",
    )
    return (
        text in CATEGORY_QUALIFIER_SUFFIXES
        or any(re.fullmatch(pattern, text) for pattern in ORGANIZATION_BRANCH_SUFFIX_PATTERNS)
        or any(re.fullmatch(pattern, text) for pattern in normal_suffix_patterns)
    )


def _consume_structured_detail_component(text: str) -> str | None:
    for keyword in STRUCTURED_DETAIL_EXACT_SUFFIXES_BY_LENGTH:
        if text.startswith(keyword):
            return text[len(keyword) :]

    for pattern in STRUCTURED_DETAIL_COMPONENT_PATTERNS:
        match = re.match(pattern, text)
        if match:
            return text[match.end() :]

    for pattern in NAMED_DETAIL_PREFIX_PATTERNS:
        match = re.match(pattern, text)
        if match and match.end() < len(text):
            return text[match.end() :]

    return None


def is_structured_location_detail_suffix(suffix: str) -> bool:
    remaining = normalized_text(suffix)
    if not remaining:
        return False

    # Accept stacked qualifiers such as "본관3층", "101동1층", "백마역1층".
    consumed = False
    while remaining:
        next_remaining = _consume_structured_detail_component(remaining)
        if next_remaining is None or next_remaining == remaining:
            return False
        consumed = True
        remaining = next_remaining
    return consumed


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


def is_single_char_entity_completion(short_norm: str, long_norm: str) -> bool:
    if len(long_norm) != len(short_norm) + 1:
        return False
    if not long_norm.startswith(short_norm):
        return False
    return any(
        long_norm.endswith(suffix) and short_norm == long_norm[:-1]
        for suffix in ENTITY_COMPLETION_SUFFIXES
    )


def is_institution_suffix_completion(short_norm: str, long_norm: str) -> bool:
    return INSTITUTION_SUFFIX_COMPLETIONS.get(short_norm) == long_norm


def is_incomplete_modifier_entity_completion(short_norm: str, long_norm: str) -> bool:
    if not long_norm.startswith(short_norm):
        return False
    if not any(short_norm.endswith(suffix) for suffix in INCOMPLETE_ENTITY_MODIFIER_SUFFIXES):
        return False
    return any(long_norm.endswith(suffix) for suffix in ENTITY_COMPLETION_SUFFIXES)


def is_high_confidence_truncation_pair(short_norm: str, long_norm: str) -> bool:
    return (
        is_single_char_entity_completion(short_norm, long_norm)
        or is_institution_suffix_completion(short_norm, long_norm)
        or is_incomplete_modifier_entity_completion(short_norm, long_norm)
    )


def find_institution_suffix_completion_pairs(counter: Counter[str]) -> list[tuple[str, str]]:
    normalized_values, values_by_normalized, _ = _normalized_counter_values(counter)
    pairs: list[tuple[str, str]] = []
    for source, source_norm in normalized_values.items():
        target_norm = INSTITUTION_SUFFIX_COMPLETIONS.get(source_norm)
        if not target_norm:
            continue
        for target in values_by_normalized.get(target_norm, ()):
            if source != target:
                pairs.append((source, target))
    return sorted(set(pairs))


def find_truncated_value_pairs(counter: Counter[str]) -> list[tuple[str, str]]:
    normalized_values, values_by_normalized, sorted_normalized_values = _normalized_counter_values(counter)
    candidate_pairs: list[tuple[str, str]] = []

    for short_value, short_norm in normalized_values.items():
        if len(short_norm) < SHORT_KOREAN_PREFIX_LEN:
            continue
        for long_norm in _prefixed_normalized_values(short_norm, sorted_normalized_values):
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
            is_single_char_completion = is_single_char_entity_completion(short_norm, long_norm)
            is_institution_completion = is_institution_suffix_completion(short_norm, long_norm)
            if not is_high_confidence_truncation_pair(short_norm, long_norm):
                continue
            short_count = counter[short_value]
            for long_value in values_by_normalized.get(long_norm, ()):
                if short_value == long_value:
                    continue
                if counter[long_value] <= short_count and not (
                    is_single_char_completion and counter[long_value] == short_count
                    or is_institution_completion
                ):
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

    # Allow a narrow fallback for final-character truncations like
    # "유치" -> "유치원" and "초등학" -> "초등학교" even when a short
    # prefix also matches another non-entity completion candidate.
    fallback_pairs: list[tuple[str, str]] = []
    for short_value, long_value in unique_pairs:
        short_norm = normalized_text(short_value)
        long_norm = normalized_text(long_value)
        if not is_single_char_entity_completion(short_norm, long_norm):
            continue

        eligible_longs = {
            candidate
            for candidate in long_values_by_short.get(short_value, set())
            if is_single_char_entity_completion(
                short_norm,
                normalized_text(candidate),
            )
        }
        if eligible_longs != {long_value}:
            continue

        eligible_shorts = {
            candidate
            for candidate in short_values_by_long.get(long_value, set())
            if is_single_char_entity_completion(
                normalized_text(candidate),
                long_norm,
            )
        }
        if eligible_shorts != {short_value}:
            continue

        fallback_pairs.append((short_value, long_value))

    # Also allow a narrow set of institution-type truncations where the missing
    # suffix is semantically fixed, such as "초등" -> "초등학교".
    institution_pairs: list[tuple[str, str]] = []
    for short_value, long_value in unique_pairs:
        if is_institution_suffix_completion(
            normalized_text(short_value),
            normalized_text(long_value),
        ):
            institution_pairs.append((short_value, long_value))

    return sorted(set(one_to_one_pairs + fallback_pairs + institution_pairs))


def _normalized_counter_values(
    counter: Counter[str],
) -> tuple[dict[str, str], dict[str, list[str]], list[str]]:
    normalized_values: dict[str, str] = {}
    values_by_normalized: dict[str, list[str]] = {}

    for raw_value in counter:
        value = raw_value.strip()
        if not value:
            continue
        normalized_value = normalized_text(value)
        if not normalized_value or is_numeric_like_value(normalized_value):
            continue
        normalized_values[value] = normalized_value
        values_by_normalized.setdefault(normalized_value, []).append(value)

    return normalized_values, values_by_normalized, sorted(values_by_normalized)


def _prefixed_normalized_values(prefix: str, sorted_values: list[str]):
    index = bisect_left(sorted_values, prefix)
    while index < len(sorted_values):
        candidate = sorted_values[index]
        if not candidate.startswith(prefix):
            break
        yield candidate
        index += 1
