from __future__ import annotations

from urllib.parse import parse_qsl, urlparse, urlunparse

from backend.config.io import PUBLIC_DATA_PORTAL_FILE_DOWNLOAD_PATH

from .files import safe_filename
from .remote_fetch import looks_like_html_response


def is_public_data_portal_file_page(url: str, payload: bytes, content_type: str) -> bool:
    parsed = urlparse(url)
    return (
        _is_public_data_portal_host(parsed.hostname)
        and parsed.path.rstrip("/").endswith("/fileData.do")
        and looks_like_html_response(payload, content_type)
    )


def is_public_data_portal_direct_download_url(url: str) -> bool:
    parsed = urlparse(url)
    if not _is_public_data_portal_host(parsed.hostname):
        return False
    if parsed.path.rstrip("/") != PUBLIC_DATA_PORTAL_FILE_DOWNLOAD_PATH:
        return False
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    return bool(query.get("atchFileId") and query.get("fileDetailSn"))


def public_data_portal_referer(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, "/", "", "", ""))


def public_data_portal_download_fallback_name(url: str) -> str:
    query = dict(parse_qsl(urlparse(url).query, keep_blank_values=True))
    atch_file_id = safe_filename(query.get("atchFileId", "")) or "data_go_kr_file"
    file_detail_sn = safe_filename(query.get("fileDetailSn", ""))
    return f"{atch_file_id}_{file_detail_sn}" if file_detail_sn else atch_file_id


def normalize_public_data_download_url(page_url: str, raw_url: str) -> str | None:
    from html import unescape
    from urllib.parse import urljoin

    value = unescape(raw_url).replace("\\/", "/").strip()
    if not value:
        return None
    url = urljoin(page_url, value)
    parsed = urlparse(url)
    if _is_public_data_portal_host(parsed.hostname) and parsed.path == PUBLIC_DATA_PORTAL_FILE_DOWNLOAD_PATH:
        return url
    return None


def _is_public_data_portal_host(hostname: str | None) -> bool:
    host = (hostname or "").lower()
    return host == "data.go.kr" or host.endswith(".data.go.kr")
