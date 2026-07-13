from __future__ import annotations

import os
import tempfile

from flask import Flask, Response, jsonify, request, send_file, stream_with_context
from werkzeug.exceptions import HTTPException

from .analysis_support import (
    _download_name,
    _report_download_path,
)
from .analysis_execution import analyze_prepared_datasets, stream_analysis_events
from .dataset_inputs import _prepare_request_datasets
from .dependencies import WebAdapterDependencies
from .error_support import UNEXPECTED_API_ERROR_MESSAGE
from .job_service import (
    get_analysis_job,
    get_analysis_job_result,
    resolve_analysis_artifact_download,
    submit_analysis_job,
)
from .request_utils import _request_options, _request_payload, _runtime_tmp_dir


def _expects_json_error() -> bool:
    return request.path.startswith("/api/") or request.method != "GET"


def _runs_on_vercel() -> bool:
    return bool(os.getenv("VERCEL"))


def _should_run_async(payload: dict[str, object]) -> bool:
    if _runs_on_vercel():
        return False

    value = payload.get("execution_mode") or payload.get("mode") or payload.get("run_async") or payload.get("async")
    if isinstance(value, bool):
        return value
    if value is None:
        return True
    return str(value).strip().lower() not in {"0", "false", "no", "n", "off", "sync", "synchronous"}


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(HTTPException)
    def handle_http_error(exc: HTTPException):
        if _expects_json_error():
            return jsonify({"error": exc.description or exc.name}), exc.code or 500
        return exc

    @app.errorhandler(ValueError)
    def handle_value_error(exc: ValueError):
        if _expects_json_error():
            return jsonify({"error": str(exc) or "잘못된 요청입니다."}), 400
        return str(exc) or "Bad Request", 400

    @app.errorhandler(Exception)
    def handle_unexpected_error(exc: Exception):
        app.logger.exception("Unhandled request error")
        if _expects_json_error():
            return jsonify({"error": UNEXPECTED_API_ERROR_MESSAGE}), 500
        return UNEXPECTED_API_ERROR_MESSAGE, 500


def register_api_routes(app: Flask, dependencies: WebAdapterDependencies) -> None:
    @app.get("/api/health")
    @app.get("/health")
    @app.get("/api/index")
    @app.get("/api/index.py")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/api/reports/download")
    def download_report():
        report_path = _report_download_path(request.args.get("path", ""), dependencies=dependencies)
        return send_file(
            report_path,
            as_attachment=True,
            download_name=_download_name(report_path.name, dependencies=dependencies),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    @app.get("/api/jobs/artifacts/download")
    def download_job_artifact():
        artifact = resolve_analysis_artifact_download(request.args.get("key", ""), dependencies=dependencies)
        return send_file(
            artifact.path,
            as_attachment=True,
            download_name=artifact.filename,
            mimetype=artifact.content_type,
        )

    @app.post("/api/reports/batch")
    def create_batch_report():
        payload = request.get_json(silent=True) or {}
        items = payload.get("results") or payload.get("items") or []
        if not isinstance(items, list):
            return jsonify({"error": "results는 배열 형식이어야 합니다."}), 400
        if not any(item.get("ok") and item.get("result") for item in items if isinstance(item, dict)):
            return jsonify({"error": "리포트를 생성할 성공 결과가 없습니다."}), 400
        report_path = dependencies.write_batch_error_report(
            items=[item for item in items if isinstance(item, dict)],
            output_dir=dependencies.validation_output_dir(),
        )
        return jsonify({"error_report_xlsx": report_path.name})

    @app.post("/api/analyze")
    @app.post("/analyze")
    @app.post("/api/index")
    @app.post("/api/index.py")
    def analyze():
        payload = _request_payload()
        options = _request_options(payload)

        with tempfile.TemporaryDirectory(prefix="public_data_quality_upload_", dir=_runtime_tmp_dir()) as tmp_dir:
            prepared_datasets = _prepare_request_datasets(payload, tmp_dir, dependencies=dependencies)
            if _should_run_async(payload):
                job = submit_analysis_job(
                    prepared_datasets=prepared_datasets,
                    request=options,
                    dependencies=dependencies,
                )
                return jsonify({"job": job.public_payload()}), 202
            payload, status_code = analyze_prepared_datasets(
                prepared_datasets=prepared_datasets,
                options=options,
                dependencies=dependencies,
            )
            return jsonify(payload), status_code

    @app.post("/api/jobs")
    def create_analysis_job():
        if _runs_on_vercel():
            return jsonify({"error": "비동기 분석은 로컬 Celery 실행 환경에서만 지원됩니다."}), 400

        payload = _request_payload()
        options = _request_options(payload)

        with tempfile.TemporaryDirectory(prefix="public_data_quality_upload_", dir=_runtime_tmp_dir()) as tmp_dir:
            prepared_datasets = _prepare_request_datasets(payload, tmp_dir, dependencies=dependencies)
            job = submit_analysis_job(
                prepared_datasets=prepared_datasets,
                request=options,
                dependencies=dependencies,
            )
        return jsonify({"job": job.public_payload()}), 202

    @app.get("/api/jobs/<job_id>")
    def analysis_job_status(job_id: str):
        job = get_analysis_job(job_id, dependencies=dependencies)
        if job is None:
            return jsonify({"error": "analysis job를 찾을 수 없습니다."}), 404
        return jsonify({"job": job.public_payload()})

    @app.get("/api/jobs/<job_id>/result")
    def analysis_job_result(job_id: str):
        result, job = get_analysis_job_result(job_id, dependencies=dependencies)
        if job is None:
            return jsonify({"error": "analysis job를 찾을 수 없습니다."}), 404
        if result is None:
            return jsonify({"job": job.public_payload()}), 202
        return jsonify(result)

    @app.post("/api/analyze-stream")
    @app.post("/analyze-stream")
    def analyze_stream():
        payload = _request_payload()
        options = _request_options(payload)

        tmp_manager = tempfile.TemporaryDirectory(prefix="public_data_quality_upload_", dir=_runtime_tmp_dir())
        try:
            prepared_datasets = _prepare_request_datasets(payload, tmp_manager.name, dependencies=dependencies)
        except Exception:
            tmp_manager.cleanup()
            raise

        return Response(
            stream_with_context(
                stream_analysis_events(
                    prepared_datasets=prepared_datasets,
                    options=options,
                    dependencies=dependencies,
                    cleanup=tmp_manager.cleanup,
                )
            ),
            mimetype="application/x-ndjson",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
