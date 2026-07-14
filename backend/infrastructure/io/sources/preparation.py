from __future__ import annotations

from pathlib import Path

from backend.application.dto import PreparedDataset
from backend.config.io import SUPPORTED_ARCHIVE_SUFFIXES, SUPPORTED_DATASET_SUFFIXES, SUPPORTED_UPLOAD_SUFFIXES

from .archives import extract_zip_datasets
from .payload_preparation import prepare_remote_payload
from .public_data import (
    is_public_data_portal_direct_download_url,
    is_public_data_portal_file_page,
    public_data_portal_download_fallback_name,
    public_data_portal_referer,
    resolve_public_data_portal_download_url,
)
from .remote import append_query_params, fetch_remote as _fetch_remote, normalize_http_url


def supported_upload_suffixes_label() -> str:
    return ", ".join(sorted(SUPPORTED_UPLOAD_SUFFIXES))


def prepare_saved_dataset(
    path: str | Path,
    display_name: str,
    output_dir: str | Path,
    *,
    source_type: str = "file",
) -> list[PreparedDataset]:
    dataset_path = Path(path)
    suffix = dataset_path.suffix.lower()
    if suffix in SUPPORTED_ARCHIVE_SUFFIXES:
        return extract_zip_datasets(dataset_path, display_name, Path(output_dir), source_type=source_type)
    if suffix in SUPPORTED_DATASET_SUFFIXES:
        return [PreparedDataset(display_name=display_name, path=dataset_path, source_type=source_type, response_type=suffix.lstrip("."))]
    raise ValueError(f"지원하지 않는 파일 형식입니다: {suffix or '<none>'}. 지원 형식: {supported_upload_suffixes_label()}")


def prepare_url_datasets(url: str, output_dir: str | Path) -> list[PreparedDataset]:
    normalized_url = normalize_http_url(url, "URL")
    request_url = normalized_url
    fetch_remote = _package_fetch_remote()
    fetch_headers: dict[str, str] | None = None
    fallback_name = "url_dataset"
    if is_public_data_portal_direct_download_url(normalized_url):
        fetch_headers = {"Referer": public_data_portal_referer(normalized_url)}
        fallback_name = public_data_portal_download_fallback_name(normalized_url)

    payload, content_type, content_disposition = fetch_remote(normalized_url, method="GET", headers=fetch_headers)
    if is_public_data_portal_file_page(normalized_url, payload, content_type):
        request_url = resolve_public_data_portal_download_url(
            normalized_url,
            payload,
            content_type,
            fetch_remote=fetch_remote,
        )
        if is_public_data_portal_direct_download_url(request_url):
            fallback_name = public_data_portal_download_fallback_name(request_url)
        payload, content_type, content_disposition = fetch_remote(
            request_url,
            method="GET",
            headers={"Referer": normalized_url},
        )

    return prepare_remote_payload(
        payload=payload,
        content_type=content_type,
        content_disposition=content_disposition,
        request_url=request_url,
        output_dir=Path(output_dir),
        source_type="url",
        fallback_name=fallback_name,
        prepare_saved_dataset_fn=prepare_saved_dataset,
    )


def prepare_api_datasets(
    url: str,
    output_dir: str | Path,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: str | bytes | None = None,
    params: dict[str, str] | None = None,
) -> list[PreparedDataset]:
    normalized_url = append_query_params(normalize_http_url(url, "API URL"), params or {})
    normalized_method = (method or "GET").strip().upper()
    fetch_remote = _package_fetch_remote()
    if normalized_method not in {"GET", "POST", "PUT", "PATCH"}:
        raise ValueError("API method는 GET, POST, PUT, PATCH 중 하나여야 합니다.")

    payload, content_type, content_disposition = fetch_remote(
        normalized_url,
        method=normalized_method,
        headers=headers,
        body=body,
    )
    return prepare_remote_payload(
        payload=payload,
        content_type=content_type,
        content_disposition=content_disposition,
        request_url=normalized_url,
        output_dir=Path(output_dir),
        source_type="api",
        fallback_name="api_response",
        prepare_saved_dataset_fn=prepare_saved_dataset,
    )


def _package_fetch_remote():
    from . import _fetch_remote as fetch_remote

    return fetch_remote


__all__ = [
    "PreparedDataset",
    "_fetch_remote",
    "prepare_api_datasets",
    "prepare_saved_dataset",
    "prepare_url_datasets",
    "supported_upload_suffixes_label",
]
