from __future__ import annotations

import json
import os
from pathlib import PureWindowsPath
from typing import Any

from flask import request
from werkzeug.datastructures import FileStorage


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
