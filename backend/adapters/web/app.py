from __future__ import annotations

import sys
from pathlib import Path

from flask import Flask

if __package__ in (None, ""):  # pragma: no cover
    project_root = Path(__file__).resolve().parents[3]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    __package__ = "backend.adapters.web"

from .api_routes import register_api_routes, register_error_handlers
from .frontend_routes import register_frontend_routes


def create_app() -> Flask:
    project_root = Path(__file__).resolve().parents[3]
    app = Flask(__name__, static_folder=str(project_root / "frontend" / "dist"))
    register_error_handlers(app)
    register_api_routes(app)
    register_frontend_routes(app)
    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)
