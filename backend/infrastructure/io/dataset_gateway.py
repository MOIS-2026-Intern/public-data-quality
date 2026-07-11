from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from backend.domain.entities.models import DatasetMeta

from .loaders import iter_uploaded_rows, load_dataset_meta, load_uploaded_dataset_meta


class FilesystemDatasetGateway:
    def load_dataset_meta(
        self,
        meta_csv_path: str | Path,
        *,
        dataset_id: str | None = None,
        dataset_name: str | None = None,
    ) -> DatasetMeta:
        return load_dataset_meta(meta_csv_path, dataset_id=dataset_id, dataset_name=dataset_name)

    def load_uploaded_dataset_meta(
        self,
        dataset_path: str | Path,
        *,
        dataset_name: str | None = None,
    ) -> DatasetMeta:
        return load_uploaded_dataset_meta(dataset_path, dataset_name=dataset_name)

    def iter_uploaded_rows(self, file_path: str | Path) -> Iterator[dict[str, str]]:
        return iter_uploaded_rows(file_path)
