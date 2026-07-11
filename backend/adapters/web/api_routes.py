from __future__ import annotations

import tempfile

from flask import Flask, Response, jsonify, request, send_file, stream_with_context
from werkzeug.exceptions import HTTPException

from backend.infrastructure.reporting.workbooks import write_batch_error_report

from .analysis_support import (
    _download_name,
    _report_download_path,
)
from .analysis_execution import analyze_prepared_datasets, stream_analysis_events
from .dataset_inputs import _prepare_request_datasets
from .error_support import UNEXPECTED_API_ERROR_MESSAGE
from .pipeline_service import validation_output_dir
from .request_utils import _request_options, _request_payload, _runtime_tmp_dir


def _expects_json_error() -> bool:
    return request.path.startswith("/api/") or request.method != "GET"


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


def register_api_routes(app: Flask) -> None:
    @app.get("/api/health")
    @app.get("/health")
    @app.get("/api/index")
    @app.get("/api/index.py")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/api/reports/download")
    def download_report():
        report_path = _report_download_path(request.args.get("path", ""))
        return send_file(
            report_path,
            as_attachment=True,
            download_name=_download_name(report_path.name),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    @app.post("/api/reports/batch")
    def create_batch_report():
        payload = request.get_json(silent=True) or {}
        items = payload.get("results") or payload.get("items") or []
        if not isinstance(items, list):
            return jsonify({"error": "results는 배열 형식이어야 합니다."}), 400
        if not any(item.get("ok") and item.get("result") for item in items if isinstance(item, dict)):
            return jsonify({"error": "리포트를 생성할 성공 결과가 없습니다."}), 400
        report_path = write_batch_error_report(
            items=[item for item in items if isinstance(item, dict)],
            output_dir=validation_output_dir(),
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
            prepared_datasets = _prepare_request_datasets(payload, tmp_dir)
            payload, status_code = analyze_prepared_datasets(
                prepared_datasets=prepared_datasets,
                options=options,
            )
            return jsonify(payload), status_code

    @app.post("/api/analyze-stream")
    @app.post("/analyze-stream")
    def analyze_stream():
        payload = _request_payload()
        options = _request_options(payload)

        tmp_manager = tempfile.TemporaryDirectory(prefix="public_data_quality_upload_", dir=_runtime_tmp_dir())
        try:
            prepared_datasets = _prepare_request_datasets(payload, tmp_manager.name)
        except Exception:
            tmp_manager.cleanup()
            raise

        return Response(
            stream_with_context(
                stream_analysis_events(
                    prepared_datasets=prepared_datasets,
                    options=options,
                    cleanup=tmp_manager.cleanup,
                )
            ),
            mimetype="application/x-ndjson",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
