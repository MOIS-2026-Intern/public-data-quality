from __future__ import annotations

from pathlib import Path


_ARTIFACT_TOKEN_DELIMITER = "__"


def unique_artifact_path(directory: Path, filename: str) -> Path:
    source = Path(filename)
    suffix = source.suffix
    stem = source.stem or "artifact"
    candidate = directory / f"{stem}{suffix}"
    if not candidate.exists():
        return candidate

    index = 2
    while True:
        candidate = directory / f"{stem}{_ARTIFACT_TOKEN_DELIMITER}{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def public_download_name(filename: str, *, default_suffix: str = ".xlsx") -> str:
    source = Path(filename.strip() or f"artifact{default_suffix}")
    suffix = source.suffix or default_suffix
    stem = source.stem or "artifact"
    delimiter, _, token = stem.rpartition(_ARTIFACT_TOKEN_DELIMITER)
    if delimiter and (
        token.isdigit() or (len(token) == 32 and all(character in "0123456789abcdef" for character in token))
    ):
        stem = delimiter or stem
    return f"{stem}{suffix}"
