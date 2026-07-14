from __future__ import annotations

from pathlib import Path
from typing import Callable

from backend.application.dto import PreparedDataset

from .files import ensure_suffix, response_filename, unique_path, url_filename
from .public_data import is_public_data_portal_direct_download_url
from .remote import (
    classify_remote_payload,
    decompress_remote_payload,
    looks_like_html_response,
    normalize_remote_text_payload,
)


def prepare_remote_payload(
    *,
    payload: bytes,
    content_type: str,
    content_disposition: str,
    request_url: str,
    output_dir: Path,
    source_type: str,
    fallback_name: str,
    prepare_saved_dataset_fn: Callable[..., list[PreparedDataset]],
) -> list[PreparedDataset]:
    if is_public_data_portal_direct_download_url(request_url) and looks_like_html_response(payload, content_type):
        raise ValueError(
            "공공데이터포털 직접 다운로드 URL이 파일 대신 HTML 페이지를 반환했습니다. "
            "URL의 atchFileId/fileDetailSn 값이 유효한지 확인하세요."
        )

    payload = decompress_remote_payload(payload, "")
    url_name = None if is_public_data_portal_direct_download_url(request_url) else url_filename(request_url)
    filename = response_filename(content_disposition) or url_name or fallback_name
    suffix = classify_remote_payload(payload, content_type, filename)
    stored_path = unique_path(output_dir, ensure_suffix(filename, suffix))
    stored_path.write_bytes(normalize_remote_text_payload(payload, suffix))

    prepared = prepare_saved_dataset_fn(stored_path, stored_path.name, output_dir, source_type=source_type)
    return [
        PreparedDataset(
            display_name=item.display_name,
            path=item.path,
            source_type=item.source_type,
            response_type=suffix.lstrip("."),
        )
        for item in prepared
    ]
