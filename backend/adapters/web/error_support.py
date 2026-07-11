from __future__ import annotations

import logging


UNEXPECTED_API_ERROR_MESSAGE = "서버 내부 오류가 발생했습니다."
UNEXPECTED_ANALYSIS_ERROR_MESSAGE = "분석 중 내부 오류가 발생했습니다."
STARTUP_FAILED_ERROR_MESSAGE = "Backend startup failed"

_logger = logging.getLogger(__name__)


def log_unexpected_exception(message: str) -> None:
    _logger.exception(message)


def public_exception_message(exc: Exception, *, unexpected_message: str) -> str:
    if isinstance(exc, ValueError):
        message = str(exc).strip()
        if message:
            return message
    return unexpected_message
