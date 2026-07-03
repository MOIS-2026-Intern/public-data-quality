from __future__ import annotations

import traceback

try:
    from web import app
except Exception as exc:  # pragma: no cover
    traceback.print_exc()

    from flask import Flask, jsonify

    startup_error = str(exc) or exc.__class__.__name__
    app = Flask(__name__)

    @app.route("/api", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
    @app.route("/api/<path:_path>", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
    @app.route("/", defaults={"_path": ""}, methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
    @app.route("/<path:_path>", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
    def startup_failed(_path: str = ""):
        return jsonify({"error": "Backend startup failed", "detail": startup_error}), 500
