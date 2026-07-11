from __future__ import annotations

from typing import Any

try:
    from backend.config.categorical import CATEGORICAL_LLM_CONFIDENCE_THRESHOLD
    from backend.domain.entities.models import ValidationFinding
    from backend.domain.policies.categorical import finding_key
    from backend.domain.policies.categorical.column import is_public_private_category_value
    from backend.domain.policies.categorical.text import clean_reason_text, is_specific_row_context_reason
    from backend.domain.policies.helpers import build_finding
except ImportError:  # pragma: no cover
    if (__package__ or "").split(".", 1)[0] != "services":
        raise
    from backend.config.categorical import CATEGORICAL_LLM_CONFIDENCE_THRESHOLD
    from backend.domain.entities.models import ValidationFinding
    from backend.domain.policies.categorical import finding_key
    from backend.domain.policies.categorical.column import is_public_private_category_value
    from backend.domain.policies.categorical.text import clean_reason_text, is_specific_row_context_reason
    from backend.domain.policies.helpers import build_finding


def append_row_context_findings(
    *,
    result: dict[str, Any],
    rows: list[dict[str, str]],
    columns: list[dict[str, Any]],
    findings: list[ValidationFinding],
) -> tuple[int, int]:
    existing_finding_keys = {finding_key(finding) for finding in findings}
    header_aliases = _header_aliases(columns)
    generated = _append_row_context_issues(
        result=result,
        rows=rows,
        findings=findings,
        existing_finding_keys=existing_finding_keys,
        header_aliases=header_aliases,
    )
    manual_generated = _append_row_context_manual_reviews(
        result=result,
        rows=rows,
        findings=findings,
        existing_finding_keys=existing_finding_keys,
        header_aliases=header_aliases,
    )
    return generated, manual_generated


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
) -> int:
    generated = 0
    for item in result.get("row_context_issues", []):
        parsed = _parse_row_context_item(item, rows, header_aliases)
        if parsed is None:
            continue
        row_index, column_name = parsed
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


def _append_row_context_manual_reviews(
    *,
    result: dict[str, Any],
    rows: list[dict[str, str]],
    findings: list[ValidationFinding],
    existing_finding_keys: set[tuple[str, str, str, tuple[int, ...]]],
    header_aliases: dict[str, str],
) -> int:
    generated = 0
    for item in result.get("row_context_manual_reviews", []):
        parsed = _parse_row_context_item(item, rows, header_aliases)
        if parsed is None:
            continue
        row_index, column_name = parsed
        confidence = float(item.get("confidence") or 0.0)
        if confidence < 0.50 or confidence >= CATEGORICAL_LLM_CONFIDENCE_THRESHOLD:
            continue
        related_columns = _related_columns(item, header_aliases)
        if column_name not in related_columns:
            related_columns.insert(0, column_name)
        reason = _manual_review_text(item.get("reason"))
        message = _row_context_manual_review_message(
            item=item,
            rows=rows,
            row_index=row_index,
            column_name=column_name,
            reason=reason,
        )
        evidence = [
            f"confidence:{confidence:.2f}",
            f"model:{result.get('_llm_model', '')}",
            f"stage:{result.get('_llm_stage', '')}",
            f"escalated:{bool(result.get('_llm_escalated'))}",
            "detector:llm_row_context_manual_review",
        ]
        if reason:
            evidence.append(f"reason:{reason}")
        finding = build_finding(
            column_name=column_name,
            severity="info",
            finding_type="manual_review",
            category_group="relation_consistency",
            criterion_name="logical_consistency",
            rule_id="row_context_manual_review",
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


def _manual_review_text(value: Any) -> str:
    cleaned = clean_reason_text(value)
    if cleaned:
        return cleaned

    text = " ".join(str(value or "").split())
    lowered = text.lower()
    if not text or len(text) > 300:
        return ""
    if any(token in lowered for token in ("lorem", "asdf", "n/a", "unknown")):
        return ""
    return text


def _row_context_manual_review_message(
    *,
    item: dict[str, Any],
    rows: list[dict[str, str]],
    row_index: int,
    column_name: str,
    reason: str,
) -> str:
    message = _manual_review_text(item.get("message"))
    generic_messages = {
        f"'{column_name}' 값은 행 문맥상 수동 검토가 필요합니다.",
        "행 문맥상 수동 검토가 필요합니다.",
        "수동 검토가 필요합니다.",
    }
    if message and message not in generic_messages:
        return message

    value = ""
    if 0 < row_index <= len(rows):
        value = str(rows[row_index - 1].get(column_name, "") or "").strip()
    target = f"'{value}' 값" if value else f"'{column_name}' 값"
    if reason:
        return f"{target}은 행 문맥상 수동 검토가 필요합니다: {reason}"
    return f"{target}은 행 문맥상 수동 검토가 필요합니다."


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
