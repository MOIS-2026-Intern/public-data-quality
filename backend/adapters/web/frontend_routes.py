from __future__ import annotations

from pathlib import Path

from flask import Flask, make_response, send_from_directory


def register_frontend_routes(app: Flask) -> None:
    @app.get("/", defaults={"path": ""})
    @app.get("/<path:path>")
    def frontend(path: str):
        dist_dir = Path(app.static_folder)
        if not dist_dir.exists():
            return (
                "Frontend build not found. Run `npm install --prefix frontend` and "
                "`npm run build --prefix frontend`, or use "
                "`npm run dev --prefix frontend` for development.",
                503,
            )
        if path and (dist_dir / path).exists():
            return send_from_directory(app.static_folder, path)
        response = make_response(send_from_directory(app.static_folder, "index.html"))
        response.headers["Cache-Control"] = "no-store"
        return response
