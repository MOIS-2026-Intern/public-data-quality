from __future__ import annotations

import json
import traceback


def _startup_failed_app(detail: str):
    def failed_app(environ, start_response):
        body = json.dumps(
            {"error": "Backend startup failed", "detail": detail},
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
        try:
            from .web import app as flask_app
        except ImportError as exc:
            if __package__:
                raise
            from web import app as flask_app

        return flask_app
    except Exception as exc:  # pragma: no cover
        traceback.print_exc()
        return _startup_failed_app(str(exc) or exc.__class__.__name__)


app = _load_app()
