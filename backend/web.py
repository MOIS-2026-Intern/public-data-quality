from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import traceback
import types
from pathlib import Path, PureWindowsPath
from typing import Any
from urllib.parse import unquote, urlparse

from flask import Flask, Response, abort, jsonify, make_response, request, send_file, send_from_directory, stream_with_context
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

from .core.io.sources import (
    PreparedDataset,
    SUPPORTED_UPLOAD_SUFFIXES,
    prepare_api_datasets,
    prepare_saved_dataset,
    prepare_url_datasets,
)
from .core.io.url_lists import load_url_list
from .service import (
    PIPELINE_PROGRESS_STEPS,
    REPORT_PROGRESS_STEP,
    run_pipeline,
    stream_pipeline,
    validation_output_dir,
)

MAX_URL_LIST_EXPANSION_DEPTH = 3


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


def _uploaded_url_list_files() -> list[FileStorage]:
    files = request.files.getlist("url_list_file") + request.files.getlist("url_list_files")
    return [uploaded_file for uploaded_file in files if uploaded_file and uploaded_file.filename]


def _parse_bool(value: Any, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _request_payload() -> dict[str, Any]:
    if request.is_json:
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            raise ValueError("JSON 요청 본문은 객체 형식이어야 합니다.")
        return payload

    payload: dict[str, Any] = {}
    for key in request.form:
        values = [value for value in request.form.getlist(key) if value not in (None, "")]
        if not values:
            continue
        payload[key] = values[0] if len(values) == 1 else values
    return payload


def _first_payload_value(payload: dict[str, Any], *names: str) -> Any:
    for name in names:
        value = payload.get(name)
        if isinstance(value, list):
            for item in value:
                if item not in (None, ""):
                    return item
            continue
        if value not in (None, ""):
            return value
    return None


def _payload_values(payload: dict[str, Any], *names: str, split_lines: bool = False) -> list[str]:
    values: list[str] = []
    for name in names:
        value = payload.get(name)
        if value in (None, ""):
            continue
        items = value if isinstance(value, list) else [value]
        for item in items:
            if item in (None, ""):
                continue
            text = str(item).strip()
            if not text:
                continue
            if split_lines:
                values.extend(line.strip() for line in text.splitlines() if line.strip())
            else:
                values.append(text)
    return values


def _parse_json_object_field(payload: dict[str, Any], *names: str) -> dict[str, str]:
    value = _first_payload_value(payload, *names)
    if value in (None, ""):
        return {}
    if isinstance(value, dict):
        return {str(key): str(nested_value) for key, nested_value in value.items() if nested_value is not None}
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{names[0]} 값은 JSON 객체 형식이어야 합니다.") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{names[0]} 값은 JSON 객체 형식이어야 합니다.")
    return {str(key): str(nested_value) for key, nested_value in parsed.items() if nested_value is not None}


def _parse_params_field(payload: dict[str, Any], *names: str) -> dict[str, str]:
    value = _first_payload_value(payload, *names)
    if value in (None, ""):
        return {}
    if isinstance(value, dict):
        return {str(key): str(nested_value) for key, nested_value in value.items() if nested_value is not None}

    text = str(value).strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        return {str(key): str(nested_value) for key, nested_value in parsed.items() if nested_value is not None}

    params: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        delimiter = "=" if "=" in stripped else ":" if ":" in stripped else None
        if not delimiter:
            raise ValueError(f"{names[0]} 값은 JSON 객체 또는 key=value 줄 목록이어야 합니다.")
        key, param_value = stripped.split(delimiter, 1)
        if key.strip():
            params[key.strip()] = param_value.strip()
    return params


def _parse_body_field(payload: dict[str, Any], *names: str) -> str | None:
    value = _first_payload_value(payload, *names)
    if value in (None, ""):
        return None
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _public_data_api_params(payload: dict[str, Any]) -> dict[str, str]:
    params = _parse_params_field(payload, "api_params", "params", "query_params")

    service_key = _first_payload_value(payload, "service_key", "serviceKey", "api_service_key")
    page_no = _first_payload_value(payload, "page_no", "pageNo")
    num_of_rows = _first_payload_value(payload, "num_of_rows", "numOfRows")
    response_type = _first_payload_value(payload, "api_response_type", "response_type")
    response_type_param = str(_first_payload_value(payload, "api_response_type_param") or "_type").strip()

    if service_key:
        params["serviceKey"] = str(service_key).strip()
    if page_no:
        params["pageNo"] = str(page_no).strip()
    if num_of_rows:
        params["numOfRows"] = str(num_of_rows).strip()
    if response_type and response_type_param and response_type_param.lower() != "none":
        params[response_type_param] = str(response_type).strip()
    return params


def _request_options(payload: dict[str, Any]) -> dict[str, Any]:
    openai_api_key = str(_first_payload_value(payload, "openai_api_key") or "").strip() or None
    if openai_api_key is not None:
        try:
            f"Bearer {openai_api_key}".encode("latin-1")
        except UnicodeEncodeError as exc:
            raise ValueError(
                "OpenAI API Key에 한글 등 HTTP 헤더로 보낼 수 없는 문자가 포함되어 있습니다. "
                "sk-로 시작하는 API Key를 그대로 입력하세요."
            ) from exc

    return {
        "use_llm_agents": _parse_bool(_first_payload_value(payload, "use_llm_agents"), default=False),
        "openai_api_key": openai_api_key,
        "llm_model": _first_payload_value(payload, "llm_model") or None,
        "llm_fast_model": _first_payload_value(payload, "llm_fast_model") or None,
        "llm_strong_model": _first_payload_value(payload, "llm_strong_model") or None,
    }


def _save_uploaded_file(
    *,
    uploaded_file: FileStorage,
    tmp_dir: str,
    index: int,
) -> list[PreparedDataset]:
    display_filename = _uploaded_display_filename(uploaded_file.filename)
    filename = secure_filename(display_filename) or f"uploaded_dataset_{index}.csv"
    suffix = Path(filename).suffix or Path(display_filename).suffix or ".csv"
    uploaded_path = Path(tmp_dir) / f"dataset_{index}{suffix}"
    uploaded_file.save(uploaded_path)
    return prepare_saved_dataset(uploaded_path, display_filename, tmp_dir, source_type="file")


def _load_uploaded_url_list_file(
    *,
    uploaded_file: FileStorage,
    tmp_dir: str,
    index: int,
) -> list[str]:
    display_filename = _uploaded_display_filename(uploaded_file.filename)
    filename = secure_filename(display_filename) or f"url_list_{index}.txt"
    suffix = Path(filename).suffix or Path(display_filename).suffix or ".txt"
    uploaded_path = Path(tmp_dir) / f"url_list_{index}{suffix}"
    uploaded_file.save(uploaded_path)
    return load_url_list(uploaded_path)


def _unique_values(values: list[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        unique.append(value)
        seen.add(value)
    return unique


def _is_data_download_like_url(value: str) -> bool:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False

    host = (parsed.hostname or "").lower()
    path = parsed.path.rstrip("/")
    lower_path = path.lower()
    if host == "data.go.kr" or host.endswith(".data.go.kr"):
        if lower_path == "/cmm/cmm/filedownload.do" or lower_path.endswith("/filedata.do"):
            return True

    return Path(unquote(parsed.path)).suffix.lower() in SUPPORTED_UPLOAD_SUFFIXES


def _downloadable_url_list_from_dataset(dataset: PreparedDataset) -> list[str]:
    try:
        urls = load_url_list(dataset.path, strict=True)
    except ValueError:
        return []

    urls = _unique_values(urls)
    if not urls or not all(_is_data_download_like_url(url) for url in urls):
        return []
    return urls


def _prepare_url_input_datasets(
    data_url: str,
    tmp_dir: str,
    *,
    depth: int = 0,
    seen_urls: set[str] | None = None,
) -> list[PreparedDataset]:
    seen = seen_urls if seen_urls is not None else set()
    if data_url in seen:
        return []
    seen.add(data_url)

    prepared = prepare_url_datasets(data_url, tmp_dir)
    if depth >= MAX_URL_LIST_EXPANSION_DEPTH:
        return prepared

    expanded: list[PreparedDataset] = []
    for dataset in prepared:
        nested_urls = _downloadable_url_list_from_dataset(dataset)
        if not nested_urls:
            expanded.append(dataset)
            continue

        nested_prepared: list[PreparedDataset] = []
        for nested_url in nested_urls:
            nested_prepared.extend(
                _prepare_url_input_datasets(
                    nested_url,
                    tmp_dir,
                    depth=depth + 1,
                    seen_urls=seen,
                )
            )
        expanded.extend(nested_prepared or [dataset])
    return expanded


def _prepare_request_datasets(payload: dict[str, Any], tmp_dir: str) -> list[PreparedDataset]:
    prepared: list[PreparedDataset] = []
    for index, uploaded_file in enumerate(_uploaded_files(), start=1):
        prepared.extend(_save_uploaded_file(uploaded_file=uploaded_file, tmp_dir=tmp_dir, index=index))

    source_hint = str(_first_payload_value(payload, "source_type", "input_type", "type") or "").strip().lower()
    generic_urls = _payload_values(payload, "url", "source_url", "nia_url", split_lines=True)
    uploaded_url_list_urls: list[str] = []
    if source_hint == "url":
        for index, uploaded_file in enumerate(_uploaded_url_list_files(), start=1):
            uploaded_url_list_urls.extend(
                _load_uploaded_url_list_file(uploaded_file=uploaded_file, tmp_dir=tmp_dir, index=index)
            )
    has_api_options = any(
        _first_payload_value(payload, name) is not None
        for name in (
            "api_method",
            "method",
            "api_headers",
            "headers",
            "api_body",
            "body",
            "request_body",
            "service_key",
            "serviceKey",
            "api_service_key",
            "page_no",
            "pageNo",
            "num_of_rows",
            "numOfRows",
            "api_params",
            "params",
            "query_params",
            "api_response_type",
            "response_type",
        )
    )

    data_urls = _payload_values(payload, "data_url", "dataset_url", "file_url", "download_url", split_lines=True)
    if uploaded_url_list_urls:
        data_urls.extend(uploaded_url_list_urls)
    if not data_urls and generic_urls and source_hint not in {"api", "openapi"} and not has_api_options:
        data_urls = generic_urls
    data_urls = _unique_values(data_urls)
    for data_url in data_urls:
        prepared.extend(_prepare_url_input_datasets(data_url, tmp_dir))

    api_urls = _payload_values(payload, "api_url", "apiEndpoint", "endpoint", "openapi_url", split_lines=True)
    if not api_urls and generic_urls and (source_hint in {"api", "openapi"} or has_api_options):
        api_urls = generic_urls
    api_urls = _unique_values(api_urls)
    for api_url in api_urls:
        prepared.extend(
            prepare_api_datasets(
                api_url,
                tmp_dir,
                method=str(_first_payload_value(payload, "api_method", "method") or "GET"),
                headers=_parse_json_object_field(payload, "api_headers", "headers"),
                body=_parse_body_field(payload, "api_body", "body", "request_body"),
                params=_public_data_api_params(payload),
            )
        )

    if not prepared:
        raise ValueError("분석할 입력 데이터(dataset_file, url, api_url 중 하나)가 필요합니다.")
    return prepared


def _analyze_prepared_dataset(
    *,
    dataset: PreparedDataset,
    use_llm_agents: bool,
    openai_api_key: str | None,
    llm_model: str | None,
    llm_fast_model: str | None,
    llm_strong_model: str | None,
) -> dict:
    return run_pipeline(
        uploaded_dataset_csv=str(dataset.path),
        uploaded_dataset_name=dataset.display_name,
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


def _progress_event(event_type: str, **payload) -> bytes:
    return (json.dumps({"type": event_type, **payload}, ensure_ascii=False) + "\n").encode("utf-8")


def _stage_steps(completed_stage_index: int) -> list[dict[str, str]]:
    stages = PIPELINE_PROGRESS_STEPS + (REPORT_PROGRESS_STEP,)
    total = len(stages)
    next_stage_index = completed_stage_index + 1
    return [
        {
            "id": stage_id,
            "label": label,
            "status": (
                "done"
                if index <= completed_stage_index
                else "active"
                if index == next_stage_index and completed_stage_index < total
                else "pending"
            ),
        }
        for index, (stage_id, label) in enumerate(stages, start=1)
    ]


def _report_download_path(value: str) -> Path:
    if not value:
        abort(404)
    reports_dir = (validation_output_dir() / "reports").resolve()
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = reports_dir / candidate
    resolved = candidate.resolve()
    if reports_dir not in resolved.parents and resolved != reports_dir:
        abort(404)
    if not resolved.exists() or not resolved.is_file():
        abort(404)
    return resolved


def _download_name(filename: str) -> str:
    safe_name = re.sub(r"[^0-9A-Za-z._-]+", "_", filename).strip("._")
    if not safe_name:
        safe_name = "error_report.xlsx"
    if not safe_name.lower().endswith(".xlsx"):
        safe_name = f"{Path(safe_name).stem or 'error_report'}.xlsx"
    return safe_name


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
        return jsonify(
            {
                "status": "ok",
            }
        )

    @app.get("/api/reports/download")
    def download_report():
        report_path = _report_download_path(request.args.get("path", ""))
        return send_file(
            report_path,
            as_attachment=True,
            download_name=_download_name(report_path.name),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

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
