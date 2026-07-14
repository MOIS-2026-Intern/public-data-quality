from __future__ import annotations

import zipfile
from pathlib import Path, PurePosixPath

from backend.application.dto import PreparedDataset
from backend.config.io import SUPPORTED_DATASET_SUFFIXES

from .files import safe_filename, unique_path


def extract_zip_datasets(
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
                extracted_path = unique_path(output_dir, f"{archive_stem}_{member_name}")
                with archive.open(member) as source, extracted_path.open("wb") as target:
                    while chunk := source.read(1024 * 1024):
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
    return safe_filename(name or "dataset")
