from __future__ import annotations

import tempfile
import traceback

from flask import Flask, Response, jsonify, request, send_file, stream_with_context
from werkzeug.exceptions import HTTPException

from backend.infrastructure.reporting.workbooks import write_batch_error_report

from .analysis_support import (
    _analyze_prepared_dataset,
    _batch_payload,
    _batch_summary,
    _download_name,
    _progress_event,
    _report_download_path,
    _stage_steps,
)
from .dataset_inputs import _prepare_request_datasets
from .pipeline_service import PIPELINE_PROGRESS_STEPS, REPORT_PROGRESS_STEP, stream_pipeline, validation_output_dir
from .request_utils import _request_options, _request_payload, _runtime_tmp_dir


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(HTTPException)
    def handle_http_error(exc: HTTPException):
        if request.path.startswith("/api/"):
            return jsonify({"error": exc.description or exc.name}), exc.code or 500
        return exc

    @app.errorhandler(Exception)
    def handle_unexpected_error(exc: Exception):
        traceback.print_exc()
        return jsonify({"error": str(exc) or exc.__class__.__name__}), 500


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
        return jsonify({"error_report_xlsx": str(report_path)})

    @app.post("/api/analyze")
    @app.post("/analyze")
    @app.post("/api/index")
    @app.post("/api/index.py")
    def analyze():
        try:
            payload = _request_payload()
            options = _request_options(payload)

            with tempfile.TemporaryDirectory(prefix="public_data_quality_upload_", dir=_runtime_tmp_dir()) as tmp_dir:
                prepared_datasets = _prepare_request_datasets(payload, tmp_dir)
                if len(prepared_datasets) == 1:
                    result = _analyze_prepared_dataset(dataset=prepared_datasets[0], **options)
                    return jsonify(result)

                items = []
                for dataset in prepared_datasets:
                    try:
                        result = _analyze_prepared_dataset(dataset=dataset, **options)
                        items.append({"ok": True, "filename": dataset.display_name, "result": result})
                    except Exception as exc:  # pragma: no cover
                        traceback.print_exc()
                        items.append(
                            {
                                "ok": False,
                                "filename": dataset.display_name,
                                "error": str(exc) or exc.__class__.__name__,
                            }
                        )

                summary = _batch_summary(items)
                status_code = 200 if summary["success_count"] else 400
                return jsonify(_batch_payload(items)), status_code
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:  # pragma: no cover
            traceback.print_exc()
            return jsonify({"error": str(exc) or exc.__class__.__name__}), 500

    @app.post("/api/analyze-stream")
    @app.post("/analyze-stream")
    def analyze_stream():
        try:
            payload = _request_payload()
            options = _request_options(payload)

            tmp_manager = tempfile.TemporaryDirectory(prefix="public_data_quality_upload_", dir=_runtime_tmp_dir())
            try:
                prepared_datasets = _prepare_request_datasets(payload, tmp_manager.name)
            except Exception:
                tmp_manager.cleanup()
                raise

            @stream_with_context
            def generate():
                total_files = len(prepared_datasets)
                items = []
                try:
                    yield _progress_event(
                        "progress",
                        progress=0,
                        current=0,
                        total=total_files,
                        message="분석 준비 중",
                        stage_index=0,
                        stage_total=len(PIPELINE_PROGRESS_STEPS) + 1,
                        stages=_stage_steps(0),
                    )

                    for index, dataset in enumerate(prepared_datasets, start=1):
                        display_filename = dataset.display_name
                        started_progress = int(((index - 1) / total_files) * 100)
                        yield _progress_event(
                            "progress",
                            progress=started_progress,
                            current=index - 1,
                            total=total_files,
                            filename=display_filename,
                            message="분석 중",
                            stage_index=0,
                            stage_total=len(PIPELINE_PROGRESS_STEPS) + 1,
                            stages=_stage_steps(0),
                        )

                        try:
                            result = None
                            for pipeline_event in stream_pipeline(
                                uploaded_dataset_csv=str(dataset.path),
                                uploaded_dataset_name=dataset.display_name,
                                **options,
                            ):
                                if pipeline_event.get("kind") == "result":
                                    result = pipeline_event.get("result")
                                    continue
                                if pipeline_event.get("kind") != "progress":
                                    continue

                                stage_index = int(pipeline_event.get("stage_index") or 0)
                                stage_total = int(pipeline_event.get("stage_total") or 1)
                                completed_stage_index = (
                                    stage_index - 1
                                    if pipeline_event.get("node") == REPORT_PROGRESS_STEP[0]
                                    else stage_index
                                )
                                stage_fraction = stage_index / max(1, stage_total)
                                progress = int(((index - 1 + stage_fraction) / total_files) * 100)
                                yield _progress_event(
                                    "progress",
                                    progress=min(progress, 99),
                                    current=index - 1,
                                    total=total_files,
                                    filename=display_filename,
                                    stage_label=pipeline_event.get("stage_label", ""),
                                    stage_index=stage_index,
                                    stage_total=stage_total,
                                    stages=_stage_steps(completed_stage_index),
                                    message=pipeline_event.get("message", "분석 중"),
                                )

                            if result is None:
                                raise RuntimeError("분석 결과를 생성하지 못했습니다.")
                            items.append({"ok": True, "filename": display_filename, "result": result})
                            completed_progress = int((index / total_files) * 100)
                            yield _progress_event(
                                "file_done",
                                progress=completed_progress,
                                current=index,
                                total=total_files,
                                filename=display_filename,
                                stage_index=len(PIPELINE_PROGRESS_STEPS) + 1,
                                stage_total=len(PIPELINE_PROGRESS_STEPS) + 1,
                                stages=_stage_steps(len(PIPELINE_PROGRESS_STEPS) + 1),
                                message="완료",
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
                                stage_index=len(PIPELINE_PROGRESS_STEPS) + 1,
                                stage_total=len(PIPELINE_PROGRESS_STEPS) + 1,
                                stages=_stage_steps(len(PIPELINE_PROGRESS_STEPS) + 1),
                                message="실패",
                            )

                    if len(items) == 1 and items[0].get("ok") and items[0].get("result"):
                        payload = items[0]["result"]
                    elif len(items) == 1:
                        payload = {"error": items[0].get("error") or "분석 실패"}
                    else:
                        payload = _batch_payload(items)

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
