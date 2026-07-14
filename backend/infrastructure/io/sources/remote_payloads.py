from __future__ import annotations

import gzip
import zipfile
from io import BytesIO
from pathlib import Path

from backend.config.io import REMOTE_TEXT_SUFFIXES, SUPPORTED_UPLOAD_SUFFIXES

from ..text_encoding import detect_text_encoding


def classify_remote_payload(payload: bytes, content_type: str, filename: str) -> str:
    stripped = payload.lstrip()
    if stripped.startswith(b"PK\x03\x04"):
        return ".xlsx" if _looks_like_xlsx(payload) else ".zip"
    if _looks_like_xls(stripped):
        return ".xls"

    name_suffix = Path(filename).suffix.lower()
    if name_suffix in SUPPORTED_UPLOAD_SUFFIXES:
        return name_suffix

    normalized_content_type = (content_type or "").split(";", 1)[0].strip().lower()
    if normalized_content_type in {"application/zip", "application/x-zip-compressed", "multipart/x-zip"}:
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
    raise ValueError(f"원격 데이터 응답 유형을 판별할 수 없습니다. Content-Type={content_type or '<none>'}")


def decompress_remote_payload(payload: bytes, content_encoding: str) -> bytes:
    encoding = (content_encoding or "").lower()
    if "gzip" not in encoding and not payload.startswith(b"\x1f\x8b"):
        return payload
    try:
        return gzip.decompress(payload)
    except (OSError, EOFError):
        return payload


def normalize_remote_text_payload(payload: bytes, suffix: str) -> bytes:
    if suffix not in REMOTE_TEXT_SUFFIXES:
        return payload
    encoding = detect_text_encoding(
        payload,
        error_message="원격 CSV/TXT 파일 인코딩을 판별할 수 없습니다. UTF-8 또는 CP949/EUC-KR 파일인지 확인하세요.",
    )
    return payload.decode(encoding).encode("utf-8-sig")


def _looks_like_xls(value: bytes) -> bool:
    return value.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")


def _looks_like_xlsx(value: bytes) -> bool:
    try:
        with zipfile.ZipFile(BytesIO(value)) as archive:
            names = set(archive.namelist())
    except zipfile.BadZipFile:
        return False
    return "[Content_Types].xml" in names and any(name.startswith("xl/") for name in names)
