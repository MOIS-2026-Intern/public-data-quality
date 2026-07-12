from __future__ import annotations

import re
from datetime import datetime

from .settings import DATE_PATTERNS


def parse_datetime(value: str) -> datetime | None:
    candidate = value.strip()
    if not candidate:
        return None
    if re.fullmatch(r"\d{4}\.0+", candidate):
        candidate = candidate.split(".", 1)[0]
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
