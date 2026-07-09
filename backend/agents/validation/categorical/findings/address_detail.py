from __future__ import annotations

from typing import Any, Callable

try:
    from .....core.config.constants import (
        ADDRESS_DETAIL_LLM_CONFIDENCE_THRESHOLD,
        ADDRESS_DETAIL_LLM_MAX_CANDIDATES,
    )
    from .....core.schema.models import AgentTrace, PipelineState, ValidationFinding
    from .....core.validation.columns.helpers import (
        address_context_columns,
        incomplete_detail_address_row_indexes,
        looks_detail_address_column,
    )
    from .....core.validation.helpers import build_finding
except ImportError:  # pragma: no cover
    if (__package__ or "").split(".", 1)[0] != "agents":
        raise
    from core.config.constants import (
        ADDRESS_DETAIL_LLM_CONFIDENCE_THRESHOLD,
        ADDRESS_DETAIL_LLM_MAX_CANDIDATES,
    )
    from core.schema.models import AgentTrace, PipelineState, ValidationFinding
    from core.validation.columns.helpers import (
        address_context_columns,
        incomplete_detail_address_row_indexes,
        looks_detail_address_column,
    )
    from core.validation.helpers import build_finding
from ..value_validator import LLMCategoricalValueValidator
from ..checks.text import clean_reason_text
from .utils import finding_key

TraceFactory = Callable[[str, str | None, str], AgentTrace]
DebugDetail = Callable[[], tuple[str, str]]


def address_detail_candidate_rows(
    *,
    rows: list[dict[str, str]],
    column,
    limit: int = ADDRESS_DETAIL_LLM_MAX_CANDIDATES,
) -> tuple[list[str], list[dict[str, Any]]]:
    related_columns = address_context_columns(rows, column.raw_name)
    if not related_columns:
        return [], []

    row_indexes = incomplete_detail_address_row_indexes(rows, column.raw_name, related_columns)
    candidates: list[dict[str, Any]] = []
    for row_index in row_indexes[:limit]:
        row = rows[row_index - 1]
        context_headers = [column.raw_name, *related_columns]
        candidates.append(
            {
                "row_index": row_index,
                "column_name": column.raw_name,
                "value": row.get(column.raw_name, ""),
                "values": {header: row.get(header, "") for header in context_headers},
                "candidate_reason": "detail_address_short_fragment",
            }
        )
    return related_columns, candidates


def run_llm_address_detail_validation(
    *,
    state: PipelineState,
    findings: list[ValidationFinding],
    traces: list[AgentTrace],
    validator: LLMCategoricalValueValidator | None,
    trace: TraceFactory,
    debug_detail: DebugDetail,
) -> tuple[list[ValidationFinding], list[AgentTrace]]:
    if validator is None or not validator.enabled:
        return findings, traces

    rows = state.get("validation_rows") or state.get("preview_rows", [])
    if not rows:
        return findings, traces

    dataset_meta = state["dataset_meta"]
    for column in state["columns"]:
        if not looks_detail_address_column(column):
            continue

        related_columns, candidates = address_detail_candidate_rows(rows=rows, column=column)
        if not candidates:
            continue

        result = validator.validate_address_detail_candidates(
            dataset_name=dataset_meta.dataset_name,
            provider_name=dataset_meta.provider_name,
            column_name=column.raw_name,
            related_columns=[column.raw_name, *related_columns],
            candidates=candidates,
        )
        if not result:
            llm_error, llm_preview = debug_detail()
            traces.append(
                trace(
                    "address_detail_validate",
                    column.raw_name,
                    f"llm_no_result,error={llm_error},preview={llm_preview}",
                )
            )
            continue

        generated = append_llm_address_detail_findings(
            result=result,
            rows=rows,
            column_name=column.raw_name,
            related_columns=related_columns,
            candidate_row_indexes={int(candidate["row_index"]) for candidate in candidates},
            findings=findings,
        )
        traces.append(
            trace(
                "address_detail_validate",
                column.raw_name,
                (
                    f"candidates={len(candidates)}, findings={generated}, "
                    f"overall_confidence={float(result.get('overall_confidence') or 0.0):.2f}, "
                    f"model={result.get('_llm_model', '')}, "
                    f"stage={result.get('_llm_stage', '')}, "
                    f"escalated={bool(result.get('_llm_escalated'))}"
                ),
            )
        )
    return findings, traces


def append_llm_address_detail_findings(
    *,
    result: dict[str, Any],
    rows: list[dict[str, str]],
    column_name: str,
    related_columns: list[str],
    candidate_row_indexes: set[int],
    findings: list[ValidationFinding],
) -> int:
    if result.get("_llm_stage") != "strong":
        return 0

    generated = 0
    existing_finding_keys = {finding_key(finding) for finding in findings}
    valid_related_columns = [column_name, *[name for name in related_columns if name != column_name]]
    for item in result.get("address_detail_issues", []):
        parsed = _parse_address_detail_item(item, column_name, candidate_row_indexes)
        if parsed is None:
            continue
        row_index = parsed
        confidence = float(item.get("confidence") or 0.0)
        if confidence < ADDRESS_DETAIL_LLM_CONFIDENCE_THRESHOLD:
            continue

        reason = clean_reason_text(item.get("reason")) or str(item.get("reason") or "").strip()
        if not _is_specific_address_detail_reason(reason):
            continue

        message = clean_reason_text(item.get("message"))
        if not message:
            value = rows[row_index - 1].get(column_name, "") if 0 < row_index <= len(rows) else ""
            message = f"'{value}' 값은 행 문맥상 잘렸거나 불완전한 상세주소로 판단됩니다."

        evidence = [
            f"confidence:{confidence:.2f}",
            f"model:{result.get('_llm_model', '')}",
            f"stage:{result.get('_llm_stage', '')}",
            f"escalated:{bool(result.get('_llm_escalated'))}",
            "detector:llm_incomplete_detail_address",
        ]
        if reason:
            evidence.append(f"reason:{reason}")

        finding = build_finding(
            column_name=column_name,
            severity="warning",
            category_group="domain_validity",
            criterion_name="categorical_semantic_domain",
            rule_id="categorical_value_truncated",
            message=message,
            row_indexes=[row_index],
            related_columns=valid_related_columns,
            evidence=evidence,
        )
        key = finding_key(finding)
        if key in existing_finding_keys:
            continue
        findings.append(finding)
        existing_finding_keys.add(key)
        generated += 1
    return generated


def _parse_address_detail_item(
    item: dict[str, Any],
    column_name: str,
    candidate_row_indexes: set[int],
) -> int | None:
    try:
        row_index = int(item.get("row_index"))
    except Exception:
        return None
    if row_index not in candidate_row_indexes:
        return None
    if str(item.get("column_name") or "").strip() != column_name:
        return None
    return row_index


def _is_specific_address_detail_reason(reason: str) -> bool:
    text = str(reason or "").strip()
    if not text:
        return False
    strong_markers = ("잘림", "불완전", "깨진", "조각", "누락", "중단", "끝나")
    weak_markers = ("의심", "가능", "짧", "희귀", "드묾", "특이")
    if any(marker in text for marker in weak_markers):
        return False
    return any(marker in text for marker in strong_markers)
