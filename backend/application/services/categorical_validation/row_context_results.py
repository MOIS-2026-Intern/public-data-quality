from __future__ import annotations

from collections import Counter
from typing import Any

from backend.config.categorical import (
    CATEGORICAL_LLM_CONFIDENCE_THRESHOLD,
    ROW_CONTEXT_SUM_MISMATCH_MARKERS,
)
from backend.domain.entities.models import ValidationFinding
from backend.domain.policies.categorical import finding_key
from backend.domain.policies.categorical.column import (
    is_low_ratio_sido_spacing_variant,
    is_public_private_category_value,
)
from backend.domain.policies.categorical.text import clean_reason_text, is_specific_row_context_reason
from backend.domain.policies.relationships.calculation_rules import (
    looks_sum_total_column_name,
    row_total_matches_components,
)
from backend.domain.policies.shared.findings import build_finding


def append_row_context_findings(
    *,
    result: dict[str, Any],
    rows: list[dict[str, str]],
    columns: list[dict[str, Any]],
    findings: list[ValidationFinding],
) -> tuple[int, int]:
    existing_finding_keys = {finding_key(finding) for finding in findings}
    header_aliases = _header_aliases(columns)
    columns_by_name = {
        str(column.get("raw_name") or "").strip(): column
        for column in columns
        if str(column.get("raw_name") or "").strip()
    }
    column_counters = _column_counters(rows)
    generated = _append_row_context_issues(
        result=result,
        rows=rows,
        findings=findings,
        existing_finding_keys=existing_finding_keys,
        header_aliases=header_aliases,
        columns_by_name=columns_by_name,
        column_counters=column_counters,
    )
    return generated, 0


def _header_aliases(columns: list[dict[str, Any]]) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for column in columns:
        raw_name = str(column.get("raw_name") or "").strip()
        normalized_name = str(column.get("normalized_name") or "").strip()
        if raw_name:
            aliases[raw_name] = raw_name
        if normalized_name and raw_name:
            aliases[normalized_name] = raw_name
    return aliases


def _related_columns(item: dict[str, Any], aliases: dict[str, str]) -> list[str]:
    return [
        aliases.get(str(value).strip(), "")
        for value in item.get("related_columns", [])
        if aliases.get(str(value).strip(), "")
    ]


def _append_row_context_issues(
    *,
    result: dict[str, Any],
    rows: list[dict[str, str]],
    findings: list[ValidationFinding],
    existing_finding_keys: set[tuple[str, str, str, tuple[int, ...]]],
    header_aliases: dict[str, str],
    columns_by_name: dict[str, dict[str, Any]],
    column_counters: dict[str, Counter[str]],
) -> int:
    generated = 0
    for item in result.get("row_context_issues", []):
        parsed = _parse_row_context_item(item, rows, header_aliases)
        if parsed is None:
            continue
        row_index, column_name = parsed
        value = str(rows[row_index - 1].get(column_name, "") or "").strip()
        if is_low_ratio_sido_spacing_variant(
            columns_by_name.get(column_name, {"raw_name": column_name, "normalized_name": column_name}),
            value,
            column_counters.get(column_name, Counter()),
        ):
            continue
        confidence = float(item.get("confidence") or 0.0)
        if confidence < CATEGORICAL_LLM_CONFIDENCE_THRESHOLD:
            continue
        related_columns = _related_columns(item, header_aliases)
        if len(set(related_columns)) < 2:
            continue
        reason = clean_reason_text(item.get("reason"))
        message = clean_reason_text(item.get("message"))
        if not message or not is_specific_row_context_reason(reason):
            continue
        if column_name not in related_columns:
            related_columns.insert(0, column_name)
        if _skip_verified_sum_match(
            rows=rows,
            row_index=row_index,
            column_name=column_name,
            related_columns=related_columns,
            message=message,
            reason=reason,
        ):
            continue
        evidence = [
            f"confidence:{confidence:.2f}",
            f"model:{result.get('_llm_model', '')}",
            f"stage:{result.get('_llm_stage', '')}",
            f"escalated:{bool(result.get('_llm_escalated'))}",
            "detector:llm_row_context",
        ]
        if reason:
            evidence.append(f"reason:{reason}")
        finding = build_finding(
            column_name=column_name,
            severity="warning",
            category_group="relation_consistency",
            criterion_name="logical_consistency",
            rule_id="logical_consistency",
            message=message,
            row_indexes=[row_index],
            related_columns=related_columns,
            evidence=evidence,
        )
        key = finding_key(finding)
        if key not in existing_finding_keys:
            findings.append(finding)
            existing_finding_keys.add(key)
            generated += 1
    return generated


def _skip_verified_sum_match(
    *,
    rows: list[dict[str, str]],
    row_index: int,
    column_name: str,
    related_columns: list[str],
    message: str,
    reason: str,
) -> bool:
    lowered_text = f"{message} {reason}".lower()
    if not any(marker in lowered_text for marker in ROW_CONTEXT_SUM_MISMATCH_MARKERS):
        return False
    if not (0 < row_index <= len(rows)):
        return False

    total_column_name = _sum_total_column_name(column_name, related_columns)
    if not total_column_name:
        return False

    component_names = [name for name in dict.fromkeys(related_columns) if name != total_column_name]
    matches = row_total_matches_components(
        rows[row_index - 1],
        total_column_name,
        component_names,
    )
    return matches is True


def _sum_total_column_name(column_name: str, related_columns: list[str]) -> str | None:
    if looks_sum_total_column_name(column_name):
        return column_name
    candidates = [
        name
        for name in dict.fromkeys(related_columns)
        if looks_sum_total_column_name(name)
    ]
    if len(candidates) == 1:
        return candidates[0]
    return None


def _parse_row_context_item(
    item: dict[str, Any],
    rows: list[dict[str, str]],
    header_aliases: dict[str, str],
) -> tuple[int, str] | None:
    try:
        row_index = int(item.get("row_index"))
    except Exception:
        return None
    if row_index < 1 or row_index > len(rows):
        return None

    column_name = header_aliases.get(str(item.get("column_name") or "").strip(), "")
    if not column_name:
        return None
    if is_public_private_category_value(rows[row_index - 1].get(column_name, "")):
        return None
    return row_index, column_name


def _column_counters(rows: list[dict[str, str]]) -> dict[str, Counter[str]]:
    counters: dict[str, Counter[str]] = {}
    if not rows:
        return counters

    headers = rows[0].keys()
    for header in headers:
        counter = Counter()
        for row in rows:
            value = str(row.get(header, "") or "").strip()
            if value:
                counter[value] += 1
        counters[header] = counter
    return counters
