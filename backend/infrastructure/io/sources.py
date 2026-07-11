from __future__ import annotations

import json
import re
import gzip
import zipfile
from dataclasses import dataclass
from html import unescape
from io import BytesIO
from pathlib import Path, PurePosixPath
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, quote, unquote, urlencode, urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen

from backend.config.io import (
    PUBLIC_DATA_PORTAL_DOWNLOAD_API_PATH,
    PUBLIC_DATA_PORTAL_FILE_DOWNLOAD_PATH,
    REMOTE_REQUEST_USER_AGENT,
    REMOTE_TEXT_SUFFIXES,
    REMOTE_TIMEOUT_SECONDS,
    SUPPORTED_ARCHIVE_SUFFIXES,
    SUPPORTED_DATASET_SUFFIXES,
    SUPPORTED_UPLOAD_SUFFIXES,
)
from .text_encoding import detect_text_encoding


@dataclass(frozen=True)
class PreparedDataset:
    display_name: str
    path: Path
    source_type: str
    response_type: str | None = None


@dataclass(frozen=True)
class _PublicDataDownloadCandidate:
    public_data_pk: str
    public_data_detail_pk: str
    atch_file_id: str = ""
    file_detail_sn: str = ""


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
        return _extract_zip_datasets(dataset_path, display_name, Path(output_dir), source_type=source_type)
    if suffix in SUPPORTED_DATASET_SUFFIXES:
        return [PreparedDataset(display_name=display_name, path=dataset_path, source_type=source_type, response_type=suffix.lstrip("."))]
    raise ValueError(
        f"지원하지 않는 파일 형식입니다: {suffix or '<none>'}. 지원 형식: {supported_upload_suffixes_label()}"
    )


def prepare_url_datasets(url: str, output_dir: str | Path) -> list[PreparedDataset]:
    normalized_url = _normalize_http_url(url, "URL")
    request_url = normalized_url
    fetch_headers: dict[str, str] | None = None
    fallback_name = "url_dataset"
    if _is_public_data_portal_direct_download_url(normalized_url):
        fetch_headers = {"Referer": _public_data_portal_referer(normalized_url)}
        fallback_name = _public_data_portal_download_fallback_name(normalized_url)

    payload, content_type, content_disposition = _fetch_remote(
        normalized_url,
        method="GET",
        headers=fetch_headers,
    )
    if _is_public_data_portal_file_page(normalized_url, payload, content_type):
        request_url = _resolve_public_data_portal_download_url(normalized_url, payload, content_type)
        if _is_public_data_portal_direct_download_url(request_url):
            fallback_name = _public_data_portal_download_fallback_name(request_url)
        payload, content_type, content_disposition = _fetch_remote(
            request_url,
            method="GET",
            headers={"Referer": normalized_url},
        )
    return _prepare_remote_payload(
        payload=payload,
        content_type=content_type,
        content_disposition=content_disposition,
        request_url=request_url,
        output_dir=Path(output_dir),
        source_type="url",
        fallback_name=fallback_name,
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
    normalized_url = _append_query_params(_normalize_http_url(url, "API URL"), params or {})
    normalized_method = (method or "GET").strip().upper()
    if normalized_method not in {"GET", "POST", "PUT", "PATCH"}:
        raise ValueError("API method는 GET, POST, PUT, PATCH 중 하나여야 합니다.")

    payload, content_type, content_disposition = _fetch_remote(
        normalized_url,
        method=normalized_method,
        headers=headers,
        body=body,
    )
    return _prepare_remote_payload(
        payload=payload,
        content_type=content_type,
        content_disposition=content_disposition,
        request_url=normalized_url,
        output_dir=Path(output_dir),
        source_type="api",
        fallback_name="api_response",
    )


def _normalize_http_url(value: str, label: str) -> str:
    url = (value or "").strip()
    if not url:
        raise ValueError(f"{label}이 비어 있습니다.")
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{label} 형식이 올바르지 않습니다. http 또는 https URL이어야 합니다.")
    return urlunparse(
        parsed._replace(
            netloc=_normalized_netloc(parsed, label),
            path=quote(parsed.path, safe="/%:@!$&'()*+,;="),
            params=quote(parsed.params, safe="%:@!$&'()*+,;="),
            query=quote(parsed.query, safe="%/?&=:+,;@!$'()*[]"),
            fragment=quote(parsed.fragment, safe="%/?&=:+,;@!$'()*[]"),
        )
    )


def _normalized_netloc(parsed, label: str) -> str:
    try:
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise ValueError(f"{label} 포트 형식이 올바르지 않습니다.") from exc
    if not hostname:
        return parsed.netloc

    host = hostname.encode("idna").decode("ascii")
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"

    userinfo = ""
    if parsed.username is not None:
        userinfo = quote(parsed.username, safe="")
        if parsed.password is not None:
            userinfo = f"{userinfo}:{quote(parsed.password, safe='')}"
        userinfo = f"{userinfo}@"

    port_suffix = f":{port}" if port is not None else ""
    return f"{userinfo}{host}{port_suffix}"


def _fetch_remote(
    url: str,
    *,
    method: str,
    headers: dict[str, str] | None = None,
    body: str | bytes | None = None,
) -> tuple[bytes, str, str]:
    try:
        url.encode("latin-1")
    except UnicodeEncodeError as exc:
        raise ValueError("URL에 인코딩되지 않은 문자가 남아 있습니다. 한글 경로/쿼리는 URL 인코딩 후 요청해야 합니다.") from exc

    request_headers = dict(
        _safe_header_pair(key, value)
        for key, value in {
            "User-Agent": REMOTE_REQUEST_USER_AGENT,
            "Accept": "*/*",
        }.items()
    )
    for key, value in (headers or {}).items():
        if key and value is not None:
            header_key, header_value = _safe_header_pair(key, value)
            request_headers[header_key] = header_value

    request_body: bytes | None = None
    if body not in (None, ""):
        request_body = body if isinstance(body, bytes) else str(body).encode("utf-8")
        if "Content-Type" not in request_headers and _looks_like_json_text(request_body):
            request_headers["Content-Type"] = "application/json"

    request = Request(url, data=request_body, headers=request_headers, method=method)
    try:
        with urlopen(request, timeout=REMOTE_TIMEOUT_SECONDS) as response:
            payload = response.read()
            content_type = response.headers.get("Content-Type", "")
            content_disposition = response.headers.get("Content-Disposition", "")
            content_encoding = response.headers.get("Content-Encoding", "")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise ValueError(f"원격 데이터 요청 실패: HTTP {exc.code} {detail}".strip()) from exc
    except URLError as exc:
        raise ValueError(f"원격 데이터 요청 실패: {exc.reason}") from exc

    if not payload:
        raise ValueError("원격 데이터 응답 본문이 비어 있습니다.")
    payload = _decompress_remote_payload(payload, content_encoding)
    return payload, content_type, content_disposition


def _safe_header_pair(key: object, value: object) -> tuple[str, str]:
    header_key = str(key).strip()
    header_value = str(value)
    try:
        header_key.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ValueError(f"HTTP 헤더 이름은 영문/숫자/기호만 사용할 수 있습니다: {header_key}") from exc
    try:
        header_value.encode("latin-1")
    except UnicodeEncodeError as exc:
        raise ValueError(
            f"HTTP 헤더 '{header_key}' 값에 한글 등 헤더로 보낼 수 없는 문자가 포함되어 있습니다. "
            "해당 값은 URL 파라미터 또는 요청 본문으로 전달하세요."
        ) from exc
    return header_key, header_value


def _is_public_data_portal_file_page(url: str, payload: bytes, content_type: str) -> bool:
    parsed = urlparse(url)
    if not _is_public_data_portal_host(parsed.hostname):
        return False
    if not parsed.path.rstrip("/").endswith("/fileData.do"):
        return False
    return _looks_like_html_response(payload, content_type)


def _is_public_data_portal_direct_download_url(url: str) -> bool:
    parsed = urlparse(url)
    if not _is_public_data_portal_host(parsed.hostname):
        return False
    if parsed.path.rstrip("/") != PUBLIC_DATA_PORTAL_FILE_DOWNLOAD_PATH:
        return False
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    return bool(query.get("atchFileId") and query.get("fileDetailSn"))


def _public_data_portal_referer(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, "/", "", "", ""))


def _public_data_portal_download_fallback_name(url: str) -> str:
    query = dict(parse_qsl(urlparse(url).query, keep_blank_values=True))
    atch_file_id = _safe_filename(query.get("atchFileId", "")) or "data_go_kr_file"
    file_detail_sn = _safe_filename(query.get("fileDetailSn", ""))
    return f"{atch_file_id}_{file_detail_sn}" if file_detail_sn else atch_file_id


def _resolve_public_data_portal_download_url(page_url: str, payload: bytes, content_type: str) -> str:
    html = _decode_remote_text(payload, content_type)
    for candidate in _public_data_download_candidates(page_url, html):
        download_url = _lookup_public_data_download_url(page_url, candidate)
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
        if public_data_pk and event.public_data_pk != public_data_pk:
            continue
        if event not in candidates:
            candidates.append(event)
    return candidates


def _extract_public_data_download_events(html: str) -> list[_PublicDataDownloadCandidate]:
    events: list[_PublicDataDownloadCandidate] = []
    for match in re.finditer(r"fn_fileDataDown\s*\((?P<args>.*?)\)", html, flags=re.IGNORECASE | re.DOTALL):
        args = _parse_js_call_args(match.group("args"))
        if len(args) < 2 or not args[0] or not args[1]:
            continue
        if not re.fullmatch(r"\d+", args[0]):
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


def _lookup_public_data_download_url(page_url: str, candidate: _PublicDataDownloadCandidate) -> str | None:
    response_payload: bytes
    try:
        response_payload, _, _ = _fetch_remote(
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
            url = _normalize_public_data_download_url(page_url, match.group("url"))
            if url:
                return url
    return None


def _normalize_public_data_download_url(page_url: str, raw_url: str) -> str | None:
    value = unescape(raw_url).replace("\\/", "/").strip()
    if not value:
        return None
    url = urljoin(page_url, value)
    parsed = urlparse(url)
    if _is_public_data_portal_host(parsed.hostname) and parsed.path == PUBLIC_DATA_PORTAL_FILE_DOWNLOAD_PATH:
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
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _looks_like_html_response(payload: bytes, content_type: str) -> bool:
    normalized_content_type = (content_type or "").split(";", 1)[0].strip().lower()
    if normalized_content_type in {"text/html", "application/xhtml+xml"}:
        return True
    stripped = payload.lstrip().lower()
    return stripped.startswith((b"<!doctype html", b"<html"))


def _decode_remote_text(payload: bytes, content_type: str) -> str:
    charset_match = re.search(r"charset=([A-Za-z0-9._-]+)", content_type or "", flags=re.IGNORECASE)
    encoding = charset_match.group(1) if charset_match else "utf-8"
    try:
        return payload.decode(encoding, errors="replace")
    except LookupError:
        return payload.decode("utf-8", errors="replace")


def _is_public_data_portal_host(hostname: str | None) -> bool:
    host = (hostname or "").lower()
    return host == "data.go.kr" or host.endswith(".data.go.kr")


def _append_query_params(url: str, params: dict[str, str]) -> str:
    cleaned = {str(key).strip(): str(value).strip() for key, value in params.items() if key and str(value).strip()}
    if not cleaned:
        return url

    parsed = urlparse(url)
    existing = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key not in cleaned
    ]
    query_parts = [f"{quote(key, safe='')}={quote(value, safe='')}" for key, value in existing]
    for key, value in cleaned.items():
        encoded_value = value if key.lower() == "servicekey" and "%" in value else quote(value, safe="")
        query_parts.append(f"{quote(key, safe='')}={encoded_value}")
    return urlunparse(parsed._replace(query="&".join(query_parts)))


def _prepare_remote_payload(
    *,
    payload: bytes,
    content_type: str,
    content_disposition: str,
    request_url: str,
    output_dir: Path,
    source_type: str,
    fallback_name: str,
) -> list[PreparedDataset]:
    if _is_public_data_portal_direct_download_url(request_url) and _looks_like_html_response(payload, content_type):
        raise ValueError(
            "공공데이터포털 직접 다운로드 URL이 파일 대신 HTML 페이지를 반환했습니다. "
            "URL의 atchFileId/fileDetailSn 값이 유효한지 확인하세요."
        )

    payload = _decompress_remote_payload(payload, "")
    url_filename = None if _is_public_data_portal_direct_download_url(request_url) else _url_filename(request_url)
    filename = _response_filename(content_disposition) or url_filename or fallback_name
    suffix = _classify_remote_payload(payload, content_type, filename)
    payload = _normalize_remote_text_payload(payload, suffix)
    stored_name = _ensure_suffix(filename, suffix)
    stored_path = _unique_path(output_dir, stored_name)
    stored_path.write_bytes(payload)

    prepared = prepare_saved_dataset(stored_path, stored_name, output_dir, source_type=source_type)
    return [
        PreparedDataset(
            display_name=item.display_name,
            path=item.path,
            source_type=item.source_type,
            response_type=suffix.lstrip("."),
        )
        for item in prepared
    ]


def _extract_zip_datasets(
    archive_path: Path,
    display_name: str,
    output_dir: Path,
    *,
    source_type: str,
) -> list[PreparedDataset]:
    prepared: list[PreparedDataset] = []
    archive_stem = Path(display_name).stem or archive_path.stem or "archive"
    try:
        with zipfile.ZipFile(archive_path) as archive:
            for member in archive.infolist():
                if member.is_dir():
                    continue
                member_name = _zip_member_display_name(member.filename)
                suffix = Path(member_name).suffix.lower()
                if suffix not in SUPPORTED_DATASET_SUFFIXES:
                    continue
                extracted_name = f"{archive_stem}_{member_name}"
                extracted_path = _unique_path(output_dir, extracted_name)
                with archive.open(member) as source, extracted_path.open("wb") as target:
                    while True:
                        chunk = source.read(1024 * 1024)
                        if not chunk:
                            break
                        target.write(chunk)
                prepared.append(
                    PreparedDataset(
                        display_name=f"{display_name}/{member_name}",
                        path=extracted_path,
                        source_type=source_type,
                        response_type=suffix.lstrip("."),
                    )
                )
    except zipfile.BadZipFile as exc:
        raise ValueError("ZIP 파일 형식이 올바르지 않습니다.") from exc

    if not prepared:
        raise ValueError(
            f"ZIP 내부에 지원 가능한 데이터 파일이 없습니다. 지원 형식: {', '.join(sorted(SUPPORTED_DATASET_SUFFIXES))}"
        )
    return prepared


def _zip_member_display_name(member_name: str) -> str:
    path = PurePosixPath(member_name)
    parts = [part for part in path.parts if part not in {"", ".", ".."}]
    name = "_".join(parts) if parts else path.name
    return _safe_filename(name or "dataset")


def _response_filename(content_disposition: str) -> str | None:
    if not content_disposition:
        return None
    encoded_match = re.search(
        r"filename\*=(?P<charset>[^'\";]+)''(?P<filename>[^;]+)",
        content_disposition,
        flags=re.IGNORECASE,
    )
    if encoded_match:
        return _safe_filename(
            _decode_disposition_filename(
                encoded_match.group("filename"),
                encoding=encoded_match.group("charset"),
            )
        )
    filename_match = re.search(r'filename="?([^";]+)"?', content_disposition, flags=re.IGNORECASE)
    if filename_match:
        return _safe_filename(_decode_disposition_filename(filename_match.group(1)))
    return None


def _decode_disposition_filename(value: str, encoding: str | None = None) -> str:
    raw = value.strip().strip('"')
    if encoding:
        try:
            return unquote(raw, encoding=encoding, errors="replace")
        except LookupError:
            return unquote(raw)

    decoded = unquote(raw)
    if decoded != raw:
        return decoded

    for candidate_encoding in ("utf-8", "cp949", "euc-kr"):
        try:
            return raw.encode("latin-1").decode(candidate_encoding)
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
    return raw


def _url_filename(url: str) -> str | None:
    path_name = Path(unquote(urlparse(url).path)).name
    return _safe_filename(path_name) if path_name else None


def _classify_remote_payload(payload: bytes, content_type: str, filename: str) -> str:
    stripped = payload.lstrip()
    if stripped.startswith(b"PK\x03\x04"):
        return ".xlsx" if _looks_like_xlsx(payload) else ".zip"
    if _looks_like_xls(stripped):
        return ".xls"

    name_suffix = Path(filename).suffix.lower()
    if name_suffix in SUPPORTED_UPLOAD_SUFFIXES:
        return name_suffix

    normalized_content_type = (content_type or "").split(";", 1)[0].strip().lower()
    if normalized_content_type in {
        "application/zip",
        "application/x-zip-compressed",
        "multipart/x-zip",
    }:
        return ".zip"
    if normalized_content_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
        return ".xlsx"
    if normalized_content_type == "application/vnd.ms-excel":
        return ".csv"
    if normalized_content_type in {"text/csv", "application/csv", "text/comma-separated-values"}:
        return ".csv"
    if normalized_content_type == "text/tab-separated-values":
        return ".tsv"
    if normalized_content_type in {"application/json", "text/json"} or normalized_content_type.endswith("+json"):
        return ".json"
    if normalized_content_type in {"application/x-ndjson", "application/jsonl"}:
        return ".jsonl"
    if normalized_content_type in {"application/xml", "text/xml"} or normalized_content_type.endswith("+xml"):
        return ".xml"

    if stripped.startswith((b"{", b"[")):
        return ".json"
    if stripped.startswith(b"<"):
        return ".xml"
    first_line = stripped.splitlines()[0] if stripped.splitlines() else b""
    if b"\t" in first_line:
        return ".tsv"
    if any(delimiter in first_line for delimiter in (b",", b";", b"|")):
        return ".csv"

    raise ValueError(
        f"원격 데이터 응답 유형을 판별할 수 없습니다. Content-Type={content_type or '<none>'}"
    )


def _decompress_remote_payload(payload: bytes, content_encoding: str) -> bytes:
    encoding = (content_encoding or "").lower()
    if "gzip" not in encoding and not payload.startswith(b"\x1f\x8b"):
        return payload
    try:
        return gzip.decompress(payload)
    except (OSError, EOFError):
        return payload


def _detect_remote_text_encoding(payload: bytes) -> str:
    return detect_text_encoding(
        payload,
        error_message="원격 CSV/TXT 파일 인코딩을 판별할 수 없습니다. UTF-8 또는 CP949/EUC-KR 파일인지 확인하세요.",
    )


def _normalize_remote_text_payload(payload: bytes, suffix: str) -> bytes:
    if suffix not in REMOTE_TEXT_SUFFIXES:
        return payload
    text = payload.decode(_detect_remote_text_encoding(payload))
    return text.encode("utf-8-sig")


def _ensure_suffix(filename: str, suffix: str) -> str:
    safe_name = _safe_filename(filename) or "dataset"
    if Path(safe_name).suffix.lower() == suffix:
        return safe_name
    stem = Path(safe_name).stem or safe_name
    return f"{stem}{suffix}"


def _safe_filename(filename: str) -> str:
    name = PurePosixPath(str(filename).replace("\\", "/")).name
    name = re.sub(r"[^0-9A-Za-z가-힣._-]+", "_", name).strip("._")
    return name or "dataset"


def _unique_path(output_dir: Path, filename: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_name = _safe_filename(filename)
    candidate = output_dir / safe_name
    if not candidate.exists():
        return candidate

    stem = candidate.stem or "dataset"
    suffix = candidate.suffix
    index = 2
    while True:
        next_candidate = output_dir / f"{stem}_{index}{suffix}"
        if not next_candidate.exists():
            return next_candidate
        index += 1


def _looks_like_json_text(value: bytes) -> bool:
    stripped = value.strip()
    if not stripped:
        return False
    if stripped.startswith((b"{", b"[")):
        try:
            json.loads(stripped.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return False
        return True
    return False


def _looks_like_xls(value: bytes) -> bool:
    return value.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")


def _looks_like_xlsx(value: bytes) -> bool:
    try:
        with zipfile.ZipFile(BytesIO(value)) as archive:
            names = set(archive.namelist())
    except zipfile.BadZipFile:
        return False
    return "[Content_Types].xml" in names and any(name.startswith("xl/") for name in names)
