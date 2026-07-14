from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from backend.config.io import RECORD_CONTAINER_KEYS

from .common import stringify_cell


def iter_json_rows(path: Path) -> Iterator[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig") as handle:
        yield from _json_payload_rows(json.load(handle))


def iter_jsonl_rows(path: Path) -> Iterator[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            if line.strip():
                yield from _json_payload_rows(json.loads(line))


def iter_xml_rows(path: Path) -> Iterator[dict[str, str]]:
    root = ElementTree.parse(path).getroot()
    for element in _xml_record_elements(root):
        row = _flatten_xml_element(element)
        if row:
            yield row


def headers_from_rows(rows: list[dict[str, str]]) -> list[str]:
    headers: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for header in row:
            if header not in seen:
                headers.append(header)
                seen.add(header)
    return headers


def _flatten_mapping(value: dict[str, Any], prefix: str = "") -> dict[str, str]:
    row: dict[str, str] = {}
    for key, nested_value in value.items():
        clean_key = str(key).strip()
        if not clean_key:
            continue
        path_key = f"{prefix}.{clean_key}" if prefix else clean_key
        if isinstance(nested_value, dict):
            row.update(_flatten_mapping(nested_value, path_key))
        elif isinstance(nested_value, list):
            row[path_key] = json.dumps(nested_value, ensure_ascii=False) if nested_value else ""
        else:
            row[path_key] = stringify_cell(nested_value)
    return row


def _rows_from_list(values: list[Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for value in values:
        if isinstance(value, dict):
            rows.append(_flatten_mapping(value))
        elif isinstance(value, list):
            rows.extend(_rows_from_list(value))
        else:
            rows.append({"value": stringify_cell(value)})
    return rows


def _find_records(value: Any) -> Any:
    if isinstance(value, list) or not isinstance(value, dict):
        return value

    for key in RECORD_CONTAINER_KEYS:
        if key in value:
            candidate = _find_records(value[key])
            if isinstance(candidate, list) and candidate:
                return candidate

    queue = list(value.values())
    while queue:
        candidate = queue.pop(0)
        if isinstance(candidate, list) and candidate and any(isinstance(item, dict) for item in candidate):
            return candidate
        if isinstance(candidate, dict):
            queue.extend(candidate.values())
    return value


def _json_payload_rows(payload: Any) -> list[dict[str, str]]:
    records = _find_records(payload)
    if isinstance(records, list):
        return _rows_from_list(records)
    if isinstance(records, dict):
        return [_flatten_mapping(records)]
    return [{"value": stringify_cell(records)}]


def _xml_tag_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _flatten_xml_element(element: ElementTree.Element, prefix: str = "") -> dict[str, str]:
    row: dict[str, str] = {}
    for key, value in element.attrib.items():
        attr_key = f"{prefix}.@{_xml_tag_name(key)}" if prefix else f"@{_xml_tag_name(key)}"
        row[attr_key] = stringify_cell(value)

    children = list(element)
    if not children:
        text = stringify_cell(element.text)
        if prefix and text:
            row[prefix] = text
        return row

    tag_counts: dict[str, int] = {}
    for child in children:
        child_tag = _xml_tag_name(child.tag)
        tag_counts[child_tag] = tag_counts.get(child_tag, 0) + 1

    for child in children:
        child_tag = _xml_tag_name(child.tag)
        child_key = f"{prefix}.{child_tag}" if prefix else child_tag
        if tag_counts[child_tag] > 1 and not list(child):
            current = row.get(child_key)
            child_text = stringify_cell(child.text)
            row[child_key] = child_text if current is None else f"{current}, {child_text}"
        else:
            row.update(_flatten_xml_element(child, child_key))
    return row


def _xml_record_elements(root: ElementTree.Element) -> list[ElementTree.Element]:
    preferred_tags = {"item", "row", "record", "data"}
    best: list[ElementTree.Element] = []
    best_score = -1

    for parent in root.iter():
        groups: dict[str, list[ElementTree.Element]] = {}
        for child in list(parent):
            groups.setdefault(_xml_tag_name(child.tag).lower(), []).append(child)
        for tag, elements in groups.items():
            if len(elements) < 2:
                continue
            score = len(elements) * 10 + (1000 if tag in preferred_tags else 0)
            if score > best_score:
                best = elements
                best_score = score

    if best:
        return best

    fallback = [element for element in root.iter() if _xml_tag_name(element.tag).lower() in preferred_tags and list(element)]
    return fallback or [root]
