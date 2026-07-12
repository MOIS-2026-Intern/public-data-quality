from __future__ import annotations

import sys
from pathlib import Path

# 프로젝트 루트를 Python 모듈 검색 경로에 추가
project_root = Path(__file__).resolve().parents[3]

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from flask import Flask

from backend.config.env import ensure_runtime_environment
from backend.bootstrap.web_dependencies import build_web_dependencies
from backend.adapters.web.api_routes import (
    register_api_routes,
    register_error_handlers,
)
from backend.adapters.web.frontend_routes import register_frontend_routes


def create_app() -> Flask:
    ensure_runtime_environment()
    dependencies = build_web_dependencies()
    app = Flask(
        __name__,
        static_folder=str(project_root / "frontend" / "dist"),
    )

    register_error_handlers(app)
    register_api_routes(app, dependencies)
    register_frontend_routes(app)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)
