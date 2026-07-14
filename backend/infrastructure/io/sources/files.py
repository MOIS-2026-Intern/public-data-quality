from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlparse


def ensure_suffix(filename: str, suffix: str) -> str:
    safe_name = safe_filename(filename) or "dataset"
    if Path(safe_name).suffix.lower() == suffix:
        return safe_name
    stem = Path(safe_name).stem or safe_name
    return f"{stem}{suffix}"


def response_filename(content_disposition: str) -> str | None:
    if not content_disposition:
        return None

    encoded_match = re.search(
        r"filename\*=(?P<charset>[^'\";]+)''(?P<filename>[^;]+)",
        content_disposition,
        flags=re.IGNORECASE,
    )
    if encoded_match:
        return safe_filename(
            decode_disposition_filename(
                encoded_match.group("filename"),
                encoding=encoded_match.group("charset"),
            )
        )

    filename_match = re.search(r'filename="?([^";]+)"?', content_disposition, flags=re.IGNORECASE)
    if filename_match:
        return safe_filename(decode_disposition_filename(filename_match.group(1)))
    return None


def decode_disposition_filename(value: str, encoding: str | None = None) -> str:
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


def safe_filename(filename: str) -> str:
    name = PurePosixPath(str(filename).replace("\\", "/")).name
    name = re.sub(r"[^0-9A-Za-z가-힣._-]+", "_", name).strip("._")
    return name or "dataset"


def unique_path(output_dir: Path, filename: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    candidate = output_dir / safe_filename(filename)
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


def url_filename(url: str) -> str | None:
    path_name = Path(unquote(urlparse(url).path)).name
    return safe_filename(path_name) if path_name else None
