from __future__ import annotations

import re

_SUSPICIOUS_SYMBOL_RE = re.compile(r"[�]|[?!]{2,}|[#@$%^*_={}|\\]{3,}")
_TERMINAL_PUNCTUATION_FRAGMENT_RE = re.compile(r"[&/+][A-Za-z]{1,12}[?！!]\s*$")
_BROKEN_TEXT_RE = re.compile(r"[�]")
_JAMO_SEQUENCE_RE = re.compile(r"[ㄱ-ㅎㅏ-ㅣ]{2,}")
_PHONE_DIGIT_RE = re.compile(r"^[0-9+\-() ]+$")
_MULTI_WHITESPACE_RE = re.compile(r"\s{2,}")
_STRONG_MULTI_WHITESPACE_RE = re.compile(r"\s{3,}")
_INNER_MULTI_WHITESPACE_RE = re.compile(r"\s{2,}")
_RANGE_WHITESPACE_RE = re.compile(r"\S(?P<left>\s*)[~〜∼](?P<right>\s*)\S")


def contains_broken_text(value: str) -> bool:
    return bool(_BROKEN_TEXT_RE.search(value)) or _has_disallowed_jamo_sequence(value)


def _has_disallowed_jamo_sequence(value: str) -> bool:
    text = value or ""
    for match in _JAMO_SEQUENCE_RE.finditer(text):
        opening_index = text.rfind("(", 0, match.start())
        closing_index = text.find(")", match.end())
        if opening_index != -1 and closing_index != -1:
            parenthetical = text[opening_index + 1 : closing_index]
            if re.fullmatch(r"[ㄱ-ㅎㅏ-ㅣ]{2,}[가-힣A-Za-z0-9]*", parenthetical):
                continue
        return True
    return False


def has_whitespace_issue(value: str) -> bool:
    return value != value.strip() or bool(_MULTI_WHITESPACE_RE.search(value))


def has_strong_whitespace_issue(value: str) -> bool:
    if _STRONG_MULTI_WHITESPACE_RE.search(value):
        return True
    return has_inconsistent_range_whitespace(value)


def has_inconsistent_range_whitespace(value: str) -> bool:
    for match in _RANGE_WHITESPACE_RE.finditer(value):
        left_spaces = match.group("left")
        right_spaces = match.group("right")
        if left_spaces != right_spaces and (left_spaces or right_spaces):
            return True
    return False


def describe_minor_whitespace_issue(value: str) -> list[str]:
    descriptions: list[str] = []
    if not value:
        return descriptions

    has_leading = value[:1].isspace()
    has_trailing = value[-1:].isspace()
    if has_leading and has_trailing:
        descriptions.append("문자열 맨 앞과 맨 뒤에 공백이 의심됩니다.")
    elif has_leading:
        descriptions.append("문자열 맨 앞에 공백이 의심됩니다.")
    elif has_trailing:
        descriptions.append("문자열 맨 뒤에 공백이 의심됩니다.")

    for inner_match in _INNER_MULTI_WHITESPACE_RE.finditer(value):
        start = inner_match.start()
        end = inner_match.end()
        if start == 0 or end >= len(value):
            continue
        if value[start - 1].isspace() or value[end].isspace():
            continue

        left_start = start - 1
        while left_start > 0 and not value[left_start - 1].isspace():
            left_start -= 1
        right_end = end
        while right_end < len(value) and not value[right_end].isspace():
            right_end += 1

        left = value[left_start:start].strip()
        right = value[end:right_end].strip()
        if left and right:
            descriptions.append(f"'{left}'과 '{right}' 사이에 공백 이상이 의심됩니다.")

    return descriptions


def has_special_char_issue(value: str) -> bool:
    return bool(_SUSPICIOUS_SYMBOL_RE.search(value)) or _has_disallowed_jamo_sequence(value)


def has_terminal_punctuation_fragment(value: str) -> bool:
    return bool(_TERMINAL_PUNCTUATION_FRAGMENT_RE.search(value or ""))


def looks_phone_number_text(value: str) -> bool:
    return bool(_PHONE_DIGIT_RE.match(value))
