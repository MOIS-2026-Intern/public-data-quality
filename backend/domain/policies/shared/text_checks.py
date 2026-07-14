from __future__ import annotations

import re

_SUSPICIOUS_SYMBOL_RE = re.compile(r"[�]|[ㄱ-ㅎㅏ-ㅣ]{2,}|[?!]{2,}|[#@$%^*_={}|\\]{3,}")
_BROKEN_TEXT_RE = re.compile(r"[�]|[ㄱ-ㅎㅏ-ㅣ]{2,}")
_PHONE_DIGIT_RE = re.compile(r"^[0-9+\-() ]+$")
_MULTI_WHITESPACE_RE = re.compile(r"\s{2,}")
_STRONG_MULTI_WHITESPACE_RE = re.compile(r"\s{3,}")
_INNER_MULTI_WHITESPACE_RE = re.compile(r"(?P<left>\S+)(?P<gap>\s{2,})(?P<right>\S+)")
_RANGE_WHITESPACE_RE = re.compile(r"\S(?P<left>\s*)[~〜∼](?P<right>\s*)\S")


def contains_broken_text(value: str) -> bool:
    return bool(_BROKEN_TEXT_RE.search(value))


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

    inner_match = _INNER_MULTI_WHITESPACE_RE.search(value)
    if inner_match:
        left = inner_match.group("left").strip()
        right = inner_match.group("right").strip()
        if left and right:
            descriptions.append(f"'{left}'과 '{right}' 사이에 공백 이상이 의심됩니다.")

    return descriptions


def has_special_char_issue(value: str) -> bool:
    return bool(_SUSPICIOUS_SYMBOL_RE.search(value))


def looks_phone_number_text(value: str) -> bool:
    return bool(_PHONE_DIGIT_RE.match(value))
