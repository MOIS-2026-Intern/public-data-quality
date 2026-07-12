from __future__ import annotations

import re

_SUSPICIOUS_SYMBOL_RE = re.compile(r"[�]|[ㄱ-ㅎㅏ-ㅣ]{2,}|[?!]{2,}|[#@$%^*_={}|\\]{3,}")
_BROKEN_TEXT_RE = re.compile(r"[�]|[ㄱ-ㅎㅏ-ㅣ]{2,}")
_PHONE_DIGIT_RE = re.compile(r"^[0-9+\-() ]+$")


def contains_broken_text(value: str) -> bool:
    return bool(_BROKEN_TEXT_RE.search(value))


def has_whitespace_issue(value: str) -> bool:
    return value != value.strip() or bool(re.search(r"\s{2,}", value))


def has_special_char_issue(value: str) -> bool:
    return bool(_SUSPICIOUS_SYMBOL_RE.search(value))


def looks_phone_number_text(value: str) -> bool:
    return bool(_PHONE_DIGIT_RE.match(value))
