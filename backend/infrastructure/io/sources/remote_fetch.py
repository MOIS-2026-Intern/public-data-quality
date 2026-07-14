from __future__ import annotations

import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, quote, urlparse, urlunparse
from urllib.request import Request, urlopen

from backend.config.io import REMOTE_REQUEST_USER_AGENT, REMOTE_TIMEOUT_SECONDS


def normalize_http_url(value: str, label: str) -> str:
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


def fetch_remote(
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

    request_headers = {
        key: value
        for key, value in (
            _safe_header_pair("User-Agent", REMOTE_REQUEST_USER_AGENT),
            _safe_header_pair("Accept", "*/*"),
        )
    }
    for key, value in (headers or {}).items():
        if key and value is not None:
            safe_key, safe_value = _safe_header_pair(key, value)
            request_headers[safe_key] = safe_value

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

    from .remote_payloads import decompress_remote_payload

    return decompress_remote_payload(payload, content_encoding), content_type, content_disposition


def looks_like_html_response(payload: bytes, content_type: str) -> bool:
    normalized_content_type = (content_type or "").split(";", 1)[0].strip().lower()
    if normalized_content_type in {"text/html", "application/xhtml+xml"}:
        return True
    return payload.lstrip().lower().startswith((b"<!doctype html", b"<html"))


def decode_remote_text(payload: bytes, content_type: str) -> str:
    charset_match = re.search(r"charset=([A-Za-z0-9._-]+)", content_type or "", flags=re.IGNORECASE)
    encoding = charset_match.group(1) if charset_match else "utf-8"
    try:
        return payload.decode(encoding, errors="replace")
    except LookupError:
        return payload.decode("utf-8", errors="replace")


def append_query_params(url: str, params: dict[str, str]) -> str:
    cleaned = {str(key).strip(): str(value).strip() for key, value in params.items() if key and str(value).strip()}
    if not cleaned:
        return url

    parsed = urlparse(url)
    existing = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True) if key not in cleaned]
    query_parts = [f"{quote(key, safe='')}={quote(value, safe='')}" for key, value in existing]
    for key, value in cleaned.items():
        encoded_value = value if key.lower() == "servicekey" and "%" in value else quote(value, safe="")
        query_parts.append(f"{quote(key, safe='')}={encoded_value}")
    return urlunparse(parsed._replace(query="&".join(query_parts)))


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
    return f"{userinfo}{host}{f':{port}' if port is not None else ''}"


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


def _looks_like_json_text(value: bytes) -> bool:
    stripped = value.strip()
    if not stripped or not stripped.startswith((b"{", b"[")):
        return False
    try:
        json.loads(stripped.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False
    return True
