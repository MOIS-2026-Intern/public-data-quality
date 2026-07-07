from __future__ import annotations

import re
from pathlib import Path

SUPPORTED_URL_LIST_SUFFIXES = {".txt", ".xlsx", ".xls"}
URL_PATTERN = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
TRAILING_URL_PUNCTUATION = ".,;:)]}>"


def supported_url_list_suffixes_label() -> str:
    return ", ".join(sorted(SUPPORTED_URL_LIST_SUFFIXES))


def load_url_list(file_path: str | Path) -> list[str]:
    path = Path(file_path)
    suffix = path.suffix.lower()
    if suffix == ".txt":
        urls = _urls_from_text_file(path)
    elif suffix == ".xlsx":
        urls = _urls_from_xlsx(path)
    elif suffix == ".xls":
        urls = _urls_from_xls(path)
    else:
        raise ValueError(
            f"지원하지 않는 URL 목록 파일 형식입니다: {suffix or '<none>'}. "
            f"지원 형식: {supported_url_list_suffixes_label()}"
        )

    if not urls:
        raise ValueError("업로드한 URL 목록 파일에서 http/https URL을 찾지 못했습니다.")
    return urls


def _append_unique(items: list[str], values: list[str]) -> None:
    seen = set(items)
    for value in values:
        if value in seen:
            continue
        items.append(value)
        seen.add(value)


def _extract_urls(text: str) -> list[str]:
    extracted: list[str] = []
    for match in URL_PATTERN.findall(text or ""):
        candidate = match.rstrip(TRAILING_URL_PUNCTUATION).strip()
        if candidate:
            extracted.append(candidate)
    return extracted


def _urls_from_text_file(path: Path) -> list[str]:
    urls: list[str] = []
    for line in path.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
        _append_unique(urls, _extract_urls(line))
    return urls


def _urls_from_xlsx(path: Path) -> list[str]:
    try:
        from openpyxl import load_workbook
    except ImportError as exc:  # pragma: no cover
        raise ValueError("XLSX URL 목록 업로드를 처리하려면 openpyxl이 필요합니다.") from exc

    workbook = load_workbook(path, read_only=True, data_only=True)
    urls: list[str] = []
    try:
        for worksheet in workbook.worksheets:
            for row in worksheet.iter_rows(values_only=True):
                for cell in row or ():
                    if cell in (None, ""):
                        continue
                    _append_unique(urls, _extract_urls(str(cell)))
    finally:
        workbook.close()
    return urls


def _urls_from_xls(path: Path) -> list[str]:
    try:
        import xlrd
    except ImportError as exc:  # pragma: no cover
        raise ValueError("XLS URL 목록 업로드를 처리하려면 xlrd가 필요합니다.") from exc

    workbook = xlrd.open_workbook(path)
    urls: list[str] = []
    for sheet_index in range(workbook.nsheets):
        sheet = workbook.sheet_by_index(sheet_index)
        for row_index in range(sheet.nrows):
            for value in sheet.row_values(row_index):
                if value in (None, ""):
                    continue
                _append_unique(urls, _extract_urls(str(value)))
    return urls
