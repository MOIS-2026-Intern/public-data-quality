from __future__ import annotations

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

    from flask import Flask, jsonify  # noqa: E402

    startup_error = str(exc) or exc.__class__.__name__
    app = Flask(__name__)

    @app.route("/api", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
    @app.route("/api/<path:_path>", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
    def api_startup_error(_path: str | None = None):
        return jsonify({"error": "Backend startup failed", "detail": startup_error}), 500
