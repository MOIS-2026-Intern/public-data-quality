from __future__ import annotations

import json
import os
import sys
import tempfile
import traceback
import types
from pathlib import Path, PureWindowsPath

from flask import Flask, Response, jsonify, make_response, request, send_from_directory, stream_with_context
from werkzeug.datastructures import FileStorage
from werkzeug.exceptions import HTTPException
from werkzeug.utils import secure_filename

if __package__ in (None, ""):  # pragma: no cover
    package_name = "public_data_quality_be"
    package_dir = Path(__file__).resolve().parent
    package = sys.modules.get(package_name)
    if package is None:
        package = types.ModuleType(package_name)
        package.__file__ = str(package_dir / "__init__.py")
        package.__path__ = [str(package_dir)]
        sys.modules[package_name] = package
    __package__ = package_name

from .service import default_data_paths, run_pipeline


def _uploaded_display_filename(filename: str | None) -> str:
    raw_filename = filename or "uploaded_dataset.csv"
    return PureWindowsPath(raw_filename).name or "uploaded_dataset.csv"


def _runtime_tmp_dir() -> str | None:
    if os.getenv("VERCEL"):
        return "/tmp"
    return None


def _uploaded_files() -> list[FileStorage]:
    files = request.files.getlist("dataset_file") + request.files.getlist("dataset_files")
    return [uploaded_file for uploaded_file in files if uploaded_file and uploaded_file.filename]


def _analyze_uploaded_file(
    *,
    uploaded_file: FileStorage,
    tmp_dir: str,
    index: int,
    use_llm_agents: bool,
    openai_api_key: str | None,
    llm_model: str | None,
    llm_fast_model: str | None,
    llm_strong_model: str | None,
) -> dict:
    display_filename = _uploaded_display_filename(uploaded_file.filename)
    filename = secure_filename(display_filename) or f"uploaded_dataset_{index}.csv"
    suffix = Path(filename).suffix or Path(display_filename).suffix or ".csv"
    uploaded_path = Path(tmp_dir) / f"dataset_{index}{suffix}"
    uploaded_file.save(uploaded_path)
    return run_pipeline(
        uploaded_dataset_csv=str(uploaded_path),
        uploaded_dataset_name=display_filename,
        use_llm_agents=use_llm_agents,
        openai_api_key=openai_api_key,
        llm_model=llm_model,
        llm_fast_model=llm_fast_model,
        llm_strong_model=llm_strong_model,
    )


def _analyze_saved_file(
    *,
    uploaded_path: str,
    display_filename: str,
    use_llm_agents: bool,
    openai_api_key: str | None,
    llm_model: str | None,
    llm_fast_model: str | None,
    llm_strong_model: str | None,
) -> dict:
    return run_pipeline(
        uploaded_dataset_csv=uploaded_path,
        uploaded_dataset_name=display_filename,
        use_llm_agents=use_llm_agents,
        openai_api_key=openai_api_key,
        llm_model=llm_model,
        llm_fast_model=llm_fast_model,
        llm_strong_model=llm_strong_model,
    )


def _batch_summary(items: list[dict]) -> dict:
    successful_results = [item["result"] for item in items if item.get("ok") and item.get("result")]
    failed_count = sum(1 for item in items if not item.get("ok"))
    return {
        "dataset_count": len(items),
        "success_count": len(successful_results),
        "failed_count": failed_count,
        "row_count": sum(int(result.get("summary", {}).get("row_count") or 0) for result in successful_results),
        "finding_count": sum(int(result.get("summary", {}).get("finding_count") or 0) for result in successful_results),
        "issue_finding_count": sum(
            int(result.get("summary", {}).get("issue_finding_count") or 0) for result in successful_results
        ),
        "manual_review_finding_count": sum(
            int(result.get("summary", {}).get("manual_review_finding_count") or 0) for result in successful_results
        ),
    }


def _progress_event(event_type: str, **payload) -> str:
    return json.dumps({"type": event_type, **payload}, ensure_ascii=False) + "\n"


def create_app() -> Flask:
    app = Flask(__name__, static_folder=str(Path(__file__).resolve().parent.parent / "frontend" / "dist"))

    @app.errorhandler(HTTPException)
    def handle_http_error(exc: HTTPException):
        if request.path.startswith("/api/"):
            return jsonify({"error": exc.description or exc.name}), exc.code or 500
        return exc

    @app.errorhandler(Exception)
    def handle_unexpected_error(exc: Exception):
        traceback.print_exc()
        return jsonify({"error": str(exc) or exc.__class__.__name__}), 500

    @app.get("/api/health")
    @app.get("/health")
    @app.get("/api/index")
    @app.get("/api/index.py")
    def health():
        meta_path = default_data_paths()
        return jsonify(
            {
                "status": "ok",
                "meta_csv": str(meta_path),
            }
        )

    @app.post("/api/analyze")
    @app.post("/analyze")
    @app.post("/api/index")
    @app.post("/api/index.py")
    def analyze():
        try:
            if not (request.content_type and request.content_type.startswith("multipart/form-data")):
                return jsonify({"error": "Use multipart/form-data with dataset_file"}), 400

            use_llm_agents = request.form.get("use_llm_agents", "false").lower() == "true"
            openai_api_key = (request.form.get("openai_api_key") or "").strip() or None
            llm_model = request.form.get("llm_model") or None
            llm_fast_model = request.form.get("llm_fast_model") or None
            llm_strong_model = request.form.get("llm_strong_model") or None
            uploaded_files = _uploaded_files()

            if not uploaded_files:
                return jsonify({"error": "dataset_file is required"}), 400

            with tempfile.TemporaryDirectory(prefix="public_data_quality_upload_", dir=_runtime_tmp_dir()) as tmp_dir:
                if len(uploaded_files) == 1:
                    result = _analyze_uploaded_file(
                        uploaded_file=uploaded_files[0],
                        tmp_dir=tmp_dir,
                        index=1,
                        use_llm_agents=use_llm_agents,
                        openai_api_key=openai_api_key,
                        llm_model=llm_model,
                        llm_fast_model=llm_fast_model,
                        llm_strong_model=llm_strong_model,
                    )
                    return jsonify(result)

                items = []
                for index, uploaded_file in enumerate(uploaded_files, start=1):
                    display_filename = _uploaded_display_filename(uploaded_file.filename)
                    try:
                        result = _analyze_uploaded_file(
                            uploaded_file=uploaded_file,
                            tmp_dir=tmp_dir,
                            index=index,
                            use_llm_agents=use_llm_agents,
                            openai_api_key=openai_api_key,
                            llm_model=llm_model,
                            llm_fast_model=llm_fast_model,
                            llm_strong_model=llm_strong_model,
                        )
                        items.append({"ok": True, "filename": display_filename, "result": result})
                    except Exception as exc:  # pragma: no cover
                        traceback.print_exc()
                        items.append(
                            {
                                "ok": False,
                                "filename": display_filename,
                                "error": str(exc) or exc.__class__.__name__,
                            }
                        )

                summary = _batch_summary(items)
                status_code = 200 if summary["success_count"] else 400
                return jsonify({"batch": True, "summary": summary, "results": items}), status_code
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:  # pragma: no cover
            traceback.print_exc()
            return jsonify({"error": str(exc) or exc.__class__.__name__}), 500

    @app.post("/api/analyze-stream")
    @app.post("/analyze-stream")
    def analyze_stream():
        try:
            if not (request.content_type and request.content_type.startswith("multipart/form-data")):
                return jsonify({"error": "Use multipart/form-data with dataset_file"}), 400

            use_llm_agents = request.form.get("use_llm_agents", "false").lower() == "true"
            openai_api_key = (request.form.get("openai_api_key") or "").strip() or None
            llm_model = request.form.get("llm_model") or None
            llm_fast_model = request.form.get("llm_fast_model") or None
            llm_strong_model = request.form.get("llm_strong_model") or None
            uploaded_files = _uploaded_files()

            if not uploaded_files:
                return jsonify({"error": "dataset_file is required"}), 400

            tmp_manager = tempfile.TemporaryDirectory(prefix="public_data_quality_upload_", dir=_runtime_tmp_dir())
            saved_files = []
            try:
                for index, uploaded_file in enumerate(uploaded_files, start=1):
                    display_filename = _uploaded_display_filename(uploaded_file.filename)
                    filename = secure_filename(display_filename) or f"uploaded_dataset_{index}.csv"
                    suffix = Path(filename).suffix or Path(display_filename).suffix or ".csv"
                    uploaded_path = Path(tmp_manager.name) / f"dataset_{index}{suffix}"
                    uploaded_file.save(uploaded_path)
                    saved_files.append(
                        {
                            "filename": display_filename,
                            "path": str(uploaded_path),
                        }
                    )
            except Exception:
                tmp_manager.cleanup()
                raise

            @stream_with_context
            def generate():
                total_files = len(saved_files)
                items = []
                try:
                    yield _progress_event(
                        "progress",
                        progress=0,
                        current=0,
                        total=total_files,
                        message="분석 준비 중",
                    )

                    for index, saved_file in enumerate(saved_files, start=1):
                        display_filename = saved_file["filename"]
                        started_progress = int(((index - 1) / total_files) * 100)
                        yield _progress_event(
                            "progress",
                            progress=started_progress,
                            current=index - 1,
                            total=total_files,
                            filename=display_filename,
                            message=f"{display_filename} 분석 중",
                        )

                        try:
                            result = _analyze_saved_file(
                                uploaded_path=saved_file["path"],
                                display_filename=display_filename,
                                use_llm_agents=use_llm_agents,
                                openai_api_key=openai_api_key,
                                llm_model=llm_model,
                                llm_fast_model=llm_fast_model,
                                llm_strong_model=llm_strong_model,
                            )
                            items.append({"ok": True, "filename": display_filename, "result": result})
                            completed_progress = int((index / total_files) * 100)
                            yield _progress_event(
                                "file_done",
                                progress=completed_progress,
                                current=index,
                                total=total_files,
                                filename=display_filename,
                                message=f"{display_filename} 완료",
                            )
                        except Exception as exc:  # pragma: no cover
                            traceback.print_exc()
                            items.append(
                                {
                                    "ok": False,
                                    "filename": display_filename,
                                    "error": str(exc) or exc.__class__.__name__,
                                }
                            )
                            completed_progress = int((index / total_files) * 100)
                            yield _progress_event(
                                "file_error",
                                progress=completed_progress,
                                current=index,
                                total=total_files,
                                filename=display_filename,
                                error=str(exc) or exc.__class__.__name__,
                                message=f"{display_filename} 실패",
                            )

                    if len(items) == 1 and items[0].get("ok") and items[0].get("result"):
                        payload = items[0]["result"]
                    elif len(items) == 1:
                        payload = {"error": items[0].get("error") or "분석 실패"}
                    else:
                        payload = {"batch": True, "summary": _batch_summary(items), "results": items}

                    yield _progress_event(
                        "final",
                        progress=100,
                        current=total_files,
                        total=total_files,
                        message="분석 완료",
                        payload=payload,
                    )
                finally:
                    tmp_manager.cleanup()

            return Response(
                generate(),
                mimetype="application/x-ndjson",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:  # pragma: no cover
            traceback.print_exc()
            return jsonify({"error": str(exc) or exc.__class__.__name__}), 500

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

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)
