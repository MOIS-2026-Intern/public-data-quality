from __future__ import annotations

import json
import traceback

try:
    from web import app
except Exception as exc:  # pragma: no cover
    traceback.print_exc()

    startup_error = str(exc) or exc.__class__.__name__

    def app(environ, start_response):
        body = json.dumps(
            {"error": "Backend startup failed", "detail": startup_error},
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
