from __future__ import annotations

import csv
import re
from collections import Counter
from collections.abc import Iterator
from pathlib import Path

from ..text_encoding import detect_text_encoding


def stringify_cell(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def clean_headers(values: list[object]) -> list[str]:
    return [stringify_cell(value) for value in values]


def open_text_dataset(path: Path):
    return path.open("r", encoding=_detect_text_encoding(path), newline="")


def iter_delimited_rows(path: Path, fallback_delimiter: str = ",") -> Iterator[dict[str, str]]:
    with open_text_dataset(path) as handle:
        dialect = _csv_dialect(handle, fallback_delimiter)
        reader = csv.reader(handle, dialect=dialect)
        headers = clean_headers(next(reader, []))
        for row in reader:
            yield _row_mapping(headers, row, dialect.delimiter)


def read_delimited_headers(path: Path, fallback_delimiter: str = ",") -> list[str]:
    with open_text_dataset(path) as handle:
        reader = csv.reader(handle, dialect=_csv_dialect(handle, fallback_delimiter))
        return [header.strip() for header in next(reader, []) if str(header).strip()]


def _detect_text_encoding(path: Path) -> str:
    return detect_text_encoding(
        path.read_bytes(),
        error_message="텍스트 데이터 파일 인코딩을 판별할 수 없습니다. UTF-8 또는 CP949/EUC-KR CSV로 저장해 다시 시도하세요.",
    )


def _csv_dialect(handle, fallback_delimiter: str = ","):
    sample = handle.read(8192)
    handle.seek(0)
    delimiter = _consistent_delimiter(sample, fallback_delimiter)
    if delimiter:
        dialect = csv.excel()
        dialect.delimiter = delimiter
        return dialect
    try:
        return csv.Sniffer().sniff(sample, delimiters=",\t;|")
    except csv.Error:
        dialect = csv.excel()
        dialect.delimiter = fallback_delimiter
        return dialect


def _consistent_delimiter(sample: str, fallback_delimiter: str = ",") -> str | None:
    lines = [line for line in sample.splitlines() if line.strip()][:50]
    if len(lines) < 2:
        return None

    best: tuple[float, str] | None = None
    for delimiter in dict.fromkeys(["\t", fallback_delimiter, ",", ";", "|"]):
        counts = [line.count(delimiter) for line in lines]
        positive_counts = [count for count in counts if count > 0]
        if len(positive_counts) < max(2, int(len(lines) * 0.7)):
            continue
        common_count, common_frequency = Counter(positive_counts).most_common(1)[0]
        consistency = common_frequency / len(positive_counts)
        if consistency < 0.8:
            continue

        coverage = len(positive_counts) / len(lines)
        delimiter_bias = 0.5 if delimiter == "\t" else 0.1 if delimiter == fallback_delimiter else 0
        score = coverage * 10 + consistency * 10 + min(common_count, 20) * 0.1 + delimiter_bias
        if best is None or score > best[0]:
            best = (score, delimiter)
    return best[1] if best else None


def _row_mapping(headers: list[str], values: list[object], delimiter: str) -> dict[str, str]:
    cleaned_headers = [header for header in clean_headers(headers) if header]
    cleaned_values = [stringify_cell(value) for value in values]
    repaired_values = _repair_overflow_row(cleaned_headers, cleaned_values, delimiter)
    return {header: repaired_values[index] if index < len(repaired_values) else "" for index, header in enumerate(cleaned_headers)}


def _repair_overflow_row(headers: list[str], values: list[str], delimiter: str) -> list[str]:
    if not headers:
        return []
    if len(values) <= len(headers):
        return values + [""] * (len(headers) - len(values))

    repaired = [""] * len(headers)
    left_header_index = 0
    left_value_index = 0
    while (
        left_header_index < len(headers)
        and left_value_index < len(values)
        and _is_anchor_header(headers[left_header_index])
        and _value_matches_header(headers[left_header_index], values[left_value_index])
    ):
        repaired[left_header_index] = values[left_value_index]
        left_header_index += 1
        left_value_index += 1

    right_header_index = len(headers) - 1
    right_value_index = len(values) - 1
    right_anchor_count = 0
    while (
        right_header_index >= left_header_index
        and right_value_index >= left_value_index
        and _is_anchor_header(headers[right_header_index])
        and _value_matches_header(headers[right_header_index], values[right_value_index])
    ):
        repaired[right_header_index] = values[right_value_index]
        right_header_index -= 1
        right_value_index -= 1
        right_anchor_count += 1

    if right_anchor_count == 0:
        return _merge_overflow_values(headers, values, delimiter)

    middle_headers = headers[left_header_index : right_header_index + 1]
    middle_values = values[left_value_index : right_value_index + 1]
    for offset, value in enumerate(_merge_overflow_values(middle_headers, middle_values, delimiter)):
        repaired[left_header_index + offset] = value
    return repaired


def _merge_overflow_values(headers: list[str], values: list[str], delimiter: str) -> list[str]:
    if not headers:
        return []
    if len(values) <= len(headers):
        return values + [""] * (len(headers) - len(values))

    merge_index = _overflow_merge_index(headers)
    repaired: list[str] = []
    value_index = 0
    for header_index in range(len(headers)):
        remaining_headers = len(headers) - header_index - 1
        if header_index == merge_index:
            take_count = max(1, len(values) - value_index - remaining_headers)
            repaired.append(_join_overflow_values(values[value_index : value_index + take_count], delimiter))
            value_index += take_count
            continue
        repaired.append(values[value_index] if value_index < len(values) else "")
        value_index += 1
    return repaired


def _join_overflow_values(values: list[str], delimiter: str) -> str:
    return (", " if delimiter == "," else delimiter).join(values)


def _overflow_merge_index(headers: list[str]) -> int:
    for index, header in enumerate(headers):
        if _is_free_text_header(header):
            return index
    return 0


def _normalized_header_name(header: str) -> str:
    return re.sub(r"[\s_-]+", "", str(header or "").strip().lower())


def _is_free_text_header(header: str) -> bool:
    name = _normalized_header_name(header)
    return any(marker in name for marker in ("내용", "사유", "이유", "개요", "설명", "비고", "메모", "상세", "본문", "텍스트", "제안", "name", "description", "desc", "content", "summary", "reason", "memo", "note"))


def _anchor_kind(header: str) -> str | None:
    name = _normalized_header_name(header)
    if any(marker in name for marker in ("url", "링크", "홈페이지", "사이트")):
        return "url"
    if name in {"연도", "년도", "year"} or name.endswith(("연도", "년도")):
        return "year"
    if any(marker in name for marker in ("일자", "날짜", "일시", "기준일", "시작일", "종료일", "date")) or name.endswith("일"):
        return "date"
    if any(marker in name for marker in ("연번", "순번", "코드", "번호", "식별자", "id", "key")):
        return "code"
    if name.endswith("수") or any(marker in name for marker in ("건수", "횟수", "인원", "금액", "가격", "비율", "면적", "거리", "count", "amount", "number")):
        return "number"
    return None


def _is_anchor_header(header: str) -> bool:
    return _anchor_kind(header) is not None


def _value_matches_header(header: str, value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    kind = _anchor_kind(header)
    if kind == "url":
        return bool(re.fullmatch(r"https?://\S+", text, flags=re.IGNORECASE))
    if kind == "year":
        return bool(re.fullmatch(r"\d{4}", text))
    if kind == "date":
        return bool(re.fullmatch(r"\d{4}[-/.]\d{1,2}[-/.]\d{1,2}(?:\s*\([^)]+\))?", text) or re.fullmatch(r"\d{2}[.]\d{1,2}[.]\d{1,2}[.]?", text))
    if kind == "number":
        return bool(re.fullmatch(r"-?\d{1,3}(?:,\d{3})*(?:\.\d+)?%?|-?\d+(?:\.\d+)?%?", text))
    if kind == "code":
        return bool(re.fullmatch(r"[0-9A-Za-z가-힣._:-]{1,80}", text))
    return False
