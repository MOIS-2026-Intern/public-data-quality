from __future__ import annotations

import json
import os
import sys
import tempfile
import traceback
from pathlib import Path

if os.getenv("VERCEL"):
    tempfile.tempdir = "/tmp"

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

try:
    from web import create_app  # noqa: E402

    app = create_app()
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
