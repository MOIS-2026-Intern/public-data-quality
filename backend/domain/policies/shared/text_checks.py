from __future__ import annotations

import re

_SUSPICIOUS_SYMBOL_RE = re.compile(r"[�]|[ㄱ-ㅎㅏ-ㅣ]{2,}|[?!]{2,}|[#@$%^*_={}|\\]{3,}")
_BROKEN_TEXT_RE = re.compile(r"[�]|[ㄱ-ㅎㅏ-ㅣ]{2,}")
_PHONE_DIGIT_RE = re.compile(r"^[0-9+\-() ]+$")
_MULTI_WHITESPACE_RE = re.compile(r"\s{2,}")
_STRONG_MULTI_WHITESPACE_RE = re.compile(r"\s{3,}")
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


def has_special_char_issue(value: str) -> bool:
    return bool(_SUSPICIOUS_SYMBOL_RE.search(value))


def looks_phone_number_text(value: str) -> bool:
    return bool(_PHONE_DIGIT_RE.match(value))
