from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.core.io.loaders import iter_uploaded_rows, load_uploaded_dataset_meta, load_uploaded_headers


def test_cp949_csv_headers_and_rows_are_loaded(tmp_path) -> None:
    path = tmp_path / "korean.csv"
    path.write_bytes("서비스명,주소\n유치원,서울\n초등학교,부산\n".encode("cp949"))

    assert load_uploaded_headers(path) == ["서비스명", "주소"]
    assert list(iter_uploaded_rows(path)) == [
        {"서비스명": "유치원", "주소": "서울"},
        {"서비스명": "초등학교", "주소": "부산"},
    ]


def test_cp949_csv_uploaded_meta_uses_detected_encoding(tmp_path) -> None:
    path = tmp_path / "korean.csv"
    path.write_bytes("서비스명,주소\n유치원,서울\n".encode("cp949"))

    meta = load_uploaded_dataset_meta(path)

    assert meta.response_fields == ["서비스명", "주소"]
