from __future__ import annotations

from functools import lru_cache
import re
from datetime import datetime

from .settings import DATE_PATTERNS

AMOUNT_STATUS_VALUES = {
    "무료",
    "유료",
    "문의",
    "문의요망",
    "문의바람",
    "별도문의",
    "협의",
    "협의후결정",
    "변동",
    "미정",
    "추후공개",
    "없음",
    "해당없음",
    "품절",
    "삭제",
    "메뉴삭제",
    "판매중지",
    "중단",
    "미운영",
    "운영중단",
    "이용불가",
}
AMOUNT_FRAGMENT_RE = re.compile(r"^([-+]?\d[\d,]*(?:\.\d+)?)(원|만원|천원|백원)?$")
AMOUNT_RANGE_RE = re.compile(
    r"^(?:[-+]?\d[\d,]*(?:\.\d+)?(?:원|만원|천원|백원)?[~〜∼](?:[-+]?\d[\d,]*(?:\.\d+)?(?:원|만원|천원|백원)?)?|[~〜∼][-+]?\d[\d,]*(?:\.\d+)?(?:원|만원|천원|백원)?)$"
)
AMOUNT_SEGMENT_RE = re.compile(
    r"[-+]?\d[\d,]*(?:\.\d+)?(?:원|만원|천원|백원)?(?:\([^)]{1,30}\))?"
)
AMOUNT_MULTI_VALUE_RE = re.compile(
    r"^[-+]?\d[\d,]*(?:\.\d+)?(?:원|만원|천원|백원)?(?:\([^)]{1,30}\))?(?:[/·+][-+]?\d[\d,]*(?:\.\d+)?(?:원|만원|천원|백원)?(?:\([^)]{1,30}\))?)+$"
)
AMOUNT_PAREN_NOTE_RE = re.compile(r"^[-+]?\d[\d,]*(?:\.\d+)?(?:원|만원|천원|백원)?(?:\([^)]{1,30}\))+$")


def _compact_amount_text(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def parse_datetime(value: str) -> datetime | None:
    candidate = value.strip()
    if not candidate:
        return None
    if re.fullmatch(r"\d{4}\.0+", candidate):
        candidate = candidate.split(".", 1)[0]
    return _parse_datetime_candidate(candidate)


@lru_cache(maxsize=32768)
def _parse_datetime_candidate(candidate: str) -> datetime | None:
    for pattern in DATE_PATTERNS:
        try:
            parsed = datetime.strptime(candidate, pattern)
            if pattern in {"%Y", "%Y년"} and not 1900 <= parsed.year <= 2200:
                return None
            return parsed
        except ValueError:
            continue
    return None


def parse_number(value: str) -> float | None:
    try:
        return float(value.replace(",", "").strip())
    except Exception:
        return None


def parse_amount_number(value: str) -> float | None:
    candidate = _compact_amount_text(value)
    if not candidate:
        return None

    match = AMOUNT_FRAGMENT_RE.fullmatch(candidate)
    if match is None:
        return None

    number_text, unit = match.groups()
    try:
        amount = float(number_text.replace(",", ""))
    except ValueError:
        return None

    scale = {
        None: 1.0,
        "원": 1.0,
        "백원": 100.0,
        "천원": 1000.0,
        "만원": 10000.0,
    }[unit]
    return amount * scale


def looks_plausible_amount_text(value: str) -> bool:
    candidate = _compact_amount_text(value)
    if not candidate:
        return False
    if candidate in AMOUNT_STATUS_VALUES:
        return True
    if parse_amount_number(candidate) is not None:
        return True
    if AMOUNT_RANGE_RE.fullmatch(candidate):
        return True
    if AMOUNT_MULTI_VALUE_RE.fullmatch(candidate):
        return True
    if AMOUNT_PAREN_NOTE_RE.fullmatch(candidate):
        return True

    stripped = AMOUNT_SEGMENT_RE.sub("", candidate)
    return not stripped and bool(AMOUNT_SEGMENT_RE.search(candidate))
