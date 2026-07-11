from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

if os.getenv("VERCEL"):
    tempfile.tempdir = "/tmp"

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from backend.adapters.web.error_support import STARTUP_FAILED_ERROR_MESSAGE, log_unexpected_exception


def _startup_failed_app(_detail: str):
    def failed_app(environ, start_response):
        body = json.dumps(
            {"error": STARTUP_FAILED_ERROR_MESSAGE},
            ensure_ascii=False,
        ).encode("utf-8")
        start_response(
            "500 Internal Server Error",
            [
                ("Content-Type", "application/json; charset=utf-8"),
                ("Content-Length", str(len(body))),
            ],
        )
        return [body]

    return failed_app


def _load_app():
    try:
        from backend.adapters.web.app import create_app  # noqa: E402

        return create_app()
    except Exception as exc:  # pragma: no cover
        log_unexpected_exception("Backend startup failed")
        return _startup_failed_app(str(exc) or exc.__class__.__name__)


app = _load_app()
