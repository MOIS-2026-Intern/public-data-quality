from __future__ import annotations

import json
import re
from dataclasses import dataclass
from html import unescape
from typing import Callable
from urllib.parse import urlencode, urljoin, urlparse

from backend.config.io import PUBLIC_DATA_PORTAL_DOWNLOAD_API_PATH, PUBLIC_DATA_PORTAL_FILE_DOWNLOAD_PATH

from .public_data_urls import normalize_public_data_download_url
from .remote_fetch import decode_remote_text

FetchRemote = Callable[..., tuple[bytes, str, str]]

@dataclass(frozen=True)
class _PublicDataDownloadCandidate:
    public_data_pk: str
    public_data_detail_pk: str
    atch_file_id: str = ""
    file_detail_sn: str = ""


def resolve_public_data_portal_download_url(
    page_url: str,
    payload: bytes,
    content_type: str,
    *,
    fetch_remote: FetchRemote,
) -> str:
    html = decode_remote_text(payload, content_type)
    for candidate in _public_data_download_candidates(page_url, html):
        download_url = _lookup_public_data_download_url(page_url, candidate, fetch_remote=fetch_remote)
        if download_url:
            return download_url

    direct_url = _extract_public_data_direct_download_url(page_url, html)
    if direct_url:
        return direct_url

    raise ValueError(
        "공공데이터포털 상세 페이지에서 파일 다운로드 URL을 찾지 못했습니다. "
        "직접 다운로드 URL을 입력하거나 파일을 내려받아 업로드하세요."
    )

def _public_data_download_candidates(page_url: str, html: str) -> list[_PublicDataDownloadCandidate]:
    candidates: list[_PublicDataDownloadCandidate] = []
    public_data_pk = _extract_input_value(html, "publicDataPk") or _public_data_pk_from_url(page_url)
    public_data_detail_pk = _extract_input_value(html, "publicDataDetailPk")
    events = _extract_public_data_download_events(html)

    if public_data_pk and public_data_detail_pk:
        matching_event = next(
            (
                event
                for event in events
                if event.public_data_pk == public_data_pk and event.public_data_detail_pk == public_data_detail_pk
            ),
            None,
        )
        candidates.append(
            _PublicDataDownloadCandidate(
                public_data_pk=public_data_pk,
                public_data_detail_pk=public_data_detail_pk,
                atch_file_id=matching_event.atch_file_id if matching_event else "",
                file_detail_sn=matching_event.file_detail_sn if matching_event else "",
            )
        )

    for event in events:
        if (not public_data_pk or event.public_data_pk == public_data_pk) and event not in candidates:
            candidates.append(event)
    return candidates

def _extract_public_data_download_events(html: str) -> list[_PublicDataDownloadCandidate]:
    events: list[_PublicDataDownloadCandidate] = []
    for match in re.finditer(r"fn_fileDataDown\s*\((?P<args>.*?)\)", html, flags=re.IGNORECASE | re.DOTALL):
        args = _parse_js_call_args(match.group("args"))
        if len(args) < 2 or not args[0] or not args[1] or not re.fullmatch(r"\d+", args[0]):
            continue
        events.append(
            _PublicDataDownloadCandidate(
                public_data_pk=args[0],
                public_data_detail_pk=args[1],
                atch_file_id=args[2] if len(args) > 2 else "",
                file_detail_sn=args[3] if len(args) > 3 else "",
            )
        )
    return events


def _parse_js_call_args(args_text: str) -> list[str]:
    args: list[str] = []
    for raw_arg in args_text.split(","):
        value = raw_arg.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        args.append(unescape(value.replace("\\'", "'").replace('\\"', '"')).strip())
    return args


def _lookup_public_data_download_url(
    page_url: str,
    candidate: _PublicDataDownloadCandidate,
    *,
    fetch_remote: FetchRemote,
) -> str | None:
    try:
        response_payload, _, _ = fetch_remote(
            urljoin(page_url, PUBLIC_DATA_PORTAL_DOWNLOAD_API_PATH),
            method="POST",
            headers={
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": page_url,
            },
            body=urlencode(
                {
                    "publicDataPk": candidate.public_data_pk,
                    "publicDataDetailPk": candidate.public_data_detail_pk,
                    "atchFileId": candidate.atch_file_id,
                    "fileDetailSn": candidate.file_detail_sn,
                }
            ).encode("utf-8"),
        )
    except ValueError:
        return None

    try:
        response = json.loads(response_payload.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None

    atch_file_id = _first_text(
        response.get("atchFileId"),
        _nested_value(response, "fileDataRegistVO", "atchFileId"),
        _nested_value(response, "dataSetFileDetailInfo", "atchFileId"),
        candidate.atch_file_id,
    )
    file_detail_sn = _first_text(
        response.get("fileDetailSn"),
        _nested_value(response, "fileDataRegistVO", "fileDetailSn"),
        _nested_value(response, "dataSetFileDetailInfo", "fileDetailSn"),
        candidate.file_detail_sn,
    )
    if not atch_file_id or not file_detail_sn:
        return None

    return urljoin(
        page_url,
        f"{PUBLIC_DATA_PORTAL_FILE_DOWNLOAD_PATH}?{urlencode({'atchFileId': atch_file_id, 'fileDetailSn': file_detail_sn, 'insertDataPrcus': 'N'})}",
    )


def _extract_public_data_direct_download_url(page_url: str, html: str) -> str | None:
    patterns = [
        r'"contentUrl"\s*:\s*"(?P<url>[^"]+)"',
        r"'contentUrl'\s*:\s*'(?P<url>[^']+)'",
        r"(?P<url>(?:https?://[^\"'<>\s]+)?/cmm/cmm/fileDownload\.do\?[^\"'<>\s]+)",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, html, flags=re.IGNORECASE):
            url = normalize_public_data_download_url(page_url, match.group("url"))
            if url:
                return url
    return None


def _extract_input_value(html: str, input_name: str) -> str | None:
    for match in re.finditer(r"<input\b[^>]*>", html, flags=re.IGNORECASE):
        tag = match.group(0)
        if not re.search(rf"\b(?:id|name)=['\"]{re.escape(input_name)}['\"]", tag, flags=re.IGNORECASE):
            continue
        value_match = re.search(r"\bvalue=['\"]([^'\"]*)['\"]", tag, flags=re.IGNORECASE)
        if value_match:
            return unescape(value_match.group(1)).strip()
    return None


def _public_data_pk_from_url(url: str) -> str | None:
    match = re.search(r"/(?:data|dataset)/(\d+)/fileData\.do$", urlparse(url).path)
    return match.group(1) if match else None


def _nested_value(mapping: object, *keys: str) -> object:
    current = mapping
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _first_text(*values: object) -> str | None:
    for value in values:
        if value is not None and (text := str(value).strip()):
            return text
    return None
