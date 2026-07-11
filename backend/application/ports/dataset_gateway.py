from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Protocol

from backend.domain.entities.models import DatasetMeta


class DatasetGatewayPort(Protocol):
    def load_dataset_meta(
        self,
        meta_csv_path: str | Path,
        *,
        dataset_id: str | None = None,
        dataset_name: str | None = None,
    ) -> DatasetMeta: ...

    def load_uploaded_dataset_meta(
        self,
        dataset_path: str | Path,
        *,
        dataset_name: str | None = None,
    ) -> DatasetMeta: ...

    def iter_uploaded_rows(self, file_path: str | Path) -> Iterator[dict[str, str]]: ...
