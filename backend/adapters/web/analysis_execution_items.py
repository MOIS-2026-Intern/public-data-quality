from __future__ import annotations

from typing import Any

from .analysis_support import AnalysisItem
from .error_support import (
    UNEXPECTED_ANALYSIS_ERROR_MESSAGE,
    log_unexpected_exception,
    public_exception_message,
)


def analysis_error_message(exc: Exception) -> str:
    error_message = public_exception_message(
        exc,
        unexpected_message=UNEXPECTED_ANALYSIS_ERROR_MESSAGE,
    )
    if error_message == UNEXPECTED_ANALYSIS_ERROR_MESSAGE:
        log_unexpected_exception("Dataset analysis failed unexpectedly")
    return error_message


def success_item(filename: str, result: dict[str, Any]) -> AnalysisItem:
    return {"ok": True, "filename": filename, "result": result}


def error_item(filename: str, error_message: str) -> AnalysisItem:
    return {"ok": False, "filename": filename, "error": error_message}
