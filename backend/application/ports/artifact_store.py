from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from backend.application.dto import ArtifactDownload, ArtifactRef


class ArtifactStorePort(Protocol):
    def put_file(
        self,
        local_path: str | Path,
        *,
        key: str,
        filename: str | None = None,
        content_type: str | None = None,
    ) -> ArtifactRef: ...

    def put_json(
        self,
        payload: Any,
        *,
        key: str,
        filename: str | None = None,
    ) -> ArtifactRef: ...

    def read_json(self, key: str) -> Any: ...

    def materialize(
        self,
        key: str,
        *,
        target_dir: str | Path,
        filename: str | None = None,
    ) -> Path: ...

    def resolve_download(self, key: str) -> ArtifactDownload: ...

