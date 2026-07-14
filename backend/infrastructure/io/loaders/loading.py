from __future__ import annotations

import csv
from collections.abc import Iterator
from pathlib import Path

from backend.config.uploads import (
    UPLOAD_DATASET_ID_PREFIX,
    UPLOAD_DATASET_TYPE,
    UPLOAD_PROVIDER_CODE,
    UPLOAD_PROVIDER_NAME,
    UPLOAD_SERVICE_TYPE,
    UPLOAD_UPDATE_CYCLE,
)
from backend.domain.entities.models import DatasetMeta

from .common import iter_delimited_rows, open_text_dataset, read_delimited_headers
from .spreadsheets import iter_xls_rows, iter_xlsx_rows, xls_headers, xlsx_headers
from .structured import headers_from_rows, iter_json_rows, iter_jsonl_rows, iter_xml_rows


def iter_uploaded_rows(file_path: str | Path) -> Iterator[dict[str, str]]:
    path = Path(file_path)
    suffix = path.suffix.lower()
    if suffix in {".csv", ".txt"}:
        yield from iter_delimited_rows(path, ",")
        return
    if suffix == ".tsv":
        yield from iter_delimited_rows(path, "\t")
        return
    if suffix == ".xlsx":
        yield from iter_xlsx_rows(path)
        return
    if suffix == ".xls":
        yield from iter_xls_rows(path)
        return
    if suffix == ".json":
        yield from iter_json_rows(path)
        return
    if suffix == ".jsonl":
        yield from iter_jsonl_rows(path)
        return
    if suffix == ".xml":
        yield from iter_xml_rows(path)
        return
    raise ValueError(_unsupported_file_type_message(suffix))


def load_uploaded_headers(file_path: str | Path) -> list[str]:
    path = Path(file_path)
    suffix = path.suffix.lower()
    if suffix in {".csv", ".txt"}:
        return read_delimited_headers(path, ",")
    if suffix == ".tsv":
        return read_delimited_headers(path, "\t")
    if suffix == ".xlsx":
        return xlsx_headers(path)
    if suffix == ".xls":
        return xls_headers(path)
    if suffix == ".json":
        return headers_from_rows(list(iter_json_rows(path)))
    if suffix == ".jsonl":
        return headers_from_rows(list(iter_jsonl_rows(path)))
    if suffix == ".xml":
        return headers_from_rows(list(iter_xml_rows(path)))
    raise ValueError(_unsupported_file_type_message(suffix))


def load_dataset_meta(
    csv_path: str | Path,
    dataset_id: str | None = None,
    dataset_name: str | None = None,
) -> DatasetMeta:
    path = Path(csv_path)
    with open_text_dataset(path) as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            row_id = (row.get("목록키") or "").strip()
            row_name = (row.get("목록명") or "").strip()
            if dataset_id and row_id != dataset_id:
                continue
            if dataset_name and row_name != dataset_name:
                continue
            total_rows = (row.get("전체행") or "").strip()
            return DatasetMeta(
                dataset_id=row_id,
                dataset_name=row_name,
                keywords=_split_csv_list(row.get("키워드", "")),
                provider_name=(row.get("제공기관명") or "").strip(),
                provider_code=(row.get("제공기관코드") or "").strip(),
                dataset_type=(row.get("목록유형") or "").strip(),
                service_type=(row.get("서비스 유형") or "").strip(),
                data_format=(row.get("데이터포맷") or "").strip(),
                request_fields=_split_csv_list(row.get("요청변수", "")),
                response_fields=_split_csv_list(row.get("출력결과", "")),
                update_cycle=(row.get("주기") or "").strip(),
                total_rows=int(total_rows) if total_rows.isdigit() else None,
            )
    raise ValueError(f"Dataset not found: {dataset_id or dataset_name or '<unknown>'}")


def load_uploaded_dataset_meta(file_path: str | Path, dataset_name: str | None = None) -> DatasetMeta:
    path = Path(file_path)
    suffix = path.suffix.lstrip(".").lower() or "csv"
    header = load_uploaded_headers(path)
    if not header:
        raise ValueError("Uploaded dataset has no header row.")
    return DatasetMeta(
        dataset_id=f"{UPLOAD_DATASET_ID_PREFIX}{path.stem}",
        dataset_name=dataset_name or path.stem,
        keywords=[],
        provider_name=UPLOAD_PROVIDER_NAME,
        provider_code=UPLOAD_PROVIDER_CODE,
        dataset_type=UPLOAD_DATASET_TYPE,
        service_type=UPLOAD_SERVICE_TYPE,
        data_format=suffix,
        request_fields=[],
        response_fields=[column.strip() for column in header if column.strip()],
        update_cycle=UPLOAD_UPDATE_CYCLE,
        total_rows=None,
    )


def _split_csv_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()] if value else []


def _unsupported_file_type_message(suffix: str) -> str:
    return (
        f"Unsupported file type: {suffix or '<none>'}. "
        "Supported: .csv, .tsv, .txt, .xlsx, .xls, .json, .jsonl, .xml"
    )
