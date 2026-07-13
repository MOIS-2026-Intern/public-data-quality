from __future__ import annotations

import json
import mimetypes
import shutil
from pathlib import Path, PurePosixPath
from typing import Any

from backend.application.dto import ArtifactDownload, ArtifactRef


class FilesystemArtifactStore:
    def __init__(self, root_dir: str | Path):
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def put_file(
        self,
        local_path: str | Path,
        *,
        key: str,
        filename: str | None = None,
        content_type: str | None = None,
    ) -> ArtifactRef:
        source = Path(local_path)
        target = self._path_for_key(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        return self._artifact_for_path(target, key=key, filename=filename, content_type=content_type)

    def put_json(
        self,
        payload: Any,
        *,
        key: str,
        filename: str | None = None,
    ) -> ArtifactRef:
        target = self._path_for_key(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return self._artifact_for_path(
            target,
            key=key,
            filename=filename or target.name,
            content_type="application/json; charset=utf-8",
        )

    def read_json(self, key: str) -> Any:
        return json.loads(self._path_for_key(key).read_text(encoding="utf-8"))

    def materialize(
        self,
        key: str,
        *,
        target_dir: str | Path,
        filename: str | None = None,
    ) -> Path:
        source = self._path_for_key(key)
        if not source.exists():
            raise FileNotFoundError(key)
        destination_dir = Path(target_dir)
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir.joinpath(*self._normalize_relative_path(filename or source.name).split("/"))
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        return destination

    def resolve_download(self, key: str) -> ArtifactDownload:
        path = self._path_for_key(key)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(key)
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        return ArtifactDownload(
            key=key,
            path=path,
            filename=path.name,
            content_type=content_type,
        )

    def _artifact_for_path(
        self,
        path: Path,
        *,
        key: str,
        filename: str | None,
        content_type: str | None,
    ) -> ArtifactRef:
        return ArtifactRef(
            key=self._normalize_key(key),
            filename=filename or path.name,
            content_type=content_type or mimetypes.guess_type(path.name)[0] or "application/octet-stream",
            size_bytes=path.stat().st_size,
        )

    def _path_for_key(self, key: str) -> Path:
        return self.root_dir.joinpath(*self._normalize_relative_path(key).split("/"))

    def _normalize_key(self, key: str) -> str:
        return self._normalize_relative_path(key)

    def _normalize_relative_path(self, value: str) -> str:
        candidate = PurePosixPath(str(value).strip())
        parts = [part for part in candidate.parts if part not in {"", ".", "/"}]
        if not parts or any(part == ".." for part in parts):
            raise ValueError("artifact key가 올바르지 않습니다.")
        return "/".join(parts)
