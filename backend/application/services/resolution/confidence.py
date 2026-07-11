from __future__ import annotations

from typing import Any

from backend.config.constants import LLM_RESOLUTION_CONFIDENCE


def coerce_resolution_confidence(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return LLM_RESOLUTION_CONFIDENCE
