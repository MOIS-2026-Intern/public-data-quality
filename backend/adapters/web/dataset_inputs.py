from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote, urlparse

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from backend.config.io import SUPPORTED_UPLOAD_SUFFIXES, URL_LIST_MAX_EXPANSION_DEPTH
from backend.infrastructure.io.sources import (
    PreparedDataset,
    prepare_api_datasets,
    prepare_saved_dataset,
    prepare_url_datasets,
)
from backend.infrastructure.io.url_lists import load_url_list

from .request_utils import (
    _first_payload_value,
    _parse_body_field,
    _parse_json_object_field,
    _payload_values,
    _public_data_api_params,
    _uploaded_display_filename,
    _uploaded_files,
    _uploaded_url_list_files,
)


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
    if depth >= URL_LIST_MAX_EXPANSION_DEPTH:
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


def _prepare_request_datasets(payload: dict[str, object], tmp_dir: str) -> list[PreparedDataset]:
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
