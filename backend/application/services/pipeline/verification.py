from __future__ import annotations

import json
from collections import Counter

from backend.application.dto import (
    PipelineState,
    merge_state_updates,
    pipeline_data,
    pipeline_request,
    pipeline_result,
    require_dataset_meta,
    update_pipeline_data,
    update_pipeline_result,
)
from backend.config.pipeline import VERIFICATION_STEP_NAME
from backend.config.verification import (
    DETERMINISTIC_ISSUE_RULE_IDS,
    DETERMINISTIC_TRUNCATION_DETECTORS,
    STRONG_LLM_ISSUE_RULE_IDS,
    VERIFICATION_STRONG_LLM_CONFIDENCE_THRESHOLD,
)
from .tracing import pipeline_trace


def verify_results(state: PipelineState) -> PipelineState:
    data = pipeline_data(state)
    request = pipeline_request(state)
    result_state = pipeline_result(state)
    dataset_meta = require_dataset_meta(state)
    repairs = 0
    manual_review = 0
    traces = list(result_state.agent_traces)
    raw_findings = result_state.findings
    findings = _verified_findings(raw_findings)
    suppressed_count = _suppressible_issue_count(raw_findings) - _issue_occurrence_count(findings)

    for column in data.columns:
        if column.repair_suggestion:
            repairs += 1
            column.verification_notes.append("수정 제안 생성")
        if not column.assigned_rules:
            manual_review += 1
            column.verification_notes.append("규칙 미할당")

    summary = _build_quality_summary(
        state,
        findings=findings,
        repairs=repairs,
        manual_review=manual_review,
        suppressed_count=max(suppressed_count, 0),
    )
    traces.append(
        pipeline_trace(
            VERIFICATION_STEP_NAME,
            action="verify_results",
            target=dataset_meta.dataset_id,
            detail=json.dumps(summary, ensure_ascii=False),
        )
    )
    return merge_state_updates(
        update_pipeline_data(state, columns=data.columns),
        update_pipeline_result(state, summary=summary, findings=findings, agent_traces=traces),
    )


def _verified_findings(findings: list) -> list:
    return [
        *_high_precision_issue_findings(findings),
        *_manual_review_findings(findings),
    ]


def _high_precision_issue_findings(findings: list) -> list:
    candidates = [
        finding
        for finding in findings
        if finding.finding_type == "issue"
        and bool(finding.row_indexes)
        and _is_final_issue_candidate(finding)
    ]
    garbled_cells = {
        (finding.column_name, row_index)
        for finding in candidates
        if finding.rule_id == "garbled_text"
        for row_index in finding.row_indexes
    }

    deduped = []
    seen_cells: set[tuple[str, str, int]] = set()
    for finding in candidates:
        row_indexes = []
        for row_index in finding.row_indexes:
            cell_key = (finding.rule_id, finding.column_name, row_index)
            if cell_key in seen_cells:
                continue
            if (
                finding.rule_id == "special_character_issue"
                and (finding.column_name, row_index) in garbled_cells
            ):
                continue
            row_indexes.append(row_index)
            seen_cells.add(cell_key)
        if not row_indexes:
            continue
        if row_indexes != finding.row_indexes:
            finding = finding.model_copy(update={"row_indexes": row_indexes})
        deduped.append(finding)
    return deduped


def _manual_review_findings(findings: list) -> list:
    verified = []
    seen: set[tuple[str, str, str, tuple[int, ...], tuple[str, ...]]] = set()
    for finding in findings:
        if finding.finding_type != "manual_review":
            continue
        if not _is_final_manual_review_candidate(finding):
            continue
        key = (
            finding.rule_id,
            finding.column_name,
            finding.message,
            tuple(finding.row_indexes),
            tuple(finding.related_columns),
        )
        if key in seen:
            continue
        seen.add(key)
        verified.append(finding)
    return verified


def _is_final_issue_candidate(finding) -> bool:
    if _is_deterministic_issue(finding):
        return True
    if _is_count_mapped_truncation(finding):
        return True
    if _is_deterministic_truncation(finding):
        return True
    return _is_strong_llm_issue(finding)


def _is_final_manual_review_candidate(finding) -> bool:
    return bool(finding.row_indexes) or finding.rule_id == "manual_review_required"


def _is_deterministic_issue(finding) -> bool:
    if finding.rule_id not in DETERMINISTIC_ISSUE_RULE_IDS:
        return False
    evidence = finding.evidence or []
    return not any(item.startswith("detector:llm_") or item.startswith("stage:") for item in evidence)


def _is_count_mapped_truncation(finding) -> bool:
    if finding.rule_id != "categorical_value_truncated":
        return False
    evidence = finding.evidence or []
    if "detector:prefix_truncation" not in evidence or "mapping:one_to_one" not in evidence:
        return False
    truncated_count = _evidence_int(evidence, "truncated_count")
    full_count = _evidence_int(evidence, "full_count")
    if truncated_count is None or full_count is None:
        return False
    if full_count > truncated_count:
        return True
    if "mapping:institution_suffix_completion" in evidence:
        return True
    return full_count == truncated_count and "mapping:single_char_entity_completion" in evidence


def _is_deterministic_truncation(finding) -> bool:
    if finding.rule_id != "categorical_value_truncated":
        return False
    evidence = finding.evidence or []
    return any(detector in evidence for detector in DETERMINISTIC_TRUNCATION_DETECTORS)


def _is_strong_llm_issue(finding) -> bool:
    if finding.rule_id not in STRONG_LLM_ISSUE_RULE_IDS:
        return False
    evidence = finding.evidence or []
    if "stage:strong" not in evidence:
        return False
    confidence = _evidence_float(evidence, "confidence")
    return confidence is not None and confidence >= VERIFICATION_STRONG_LLM_CONFIDENCE_THRESHOLD


def _evidence_int(evidence: list[str], key: str) -> int | None:
    raw_value = _evidence_value(evidence, key)
    if raw_value is None:
        return None
    try:
        return int(raw_value)
    except ValueError:
        return None


def _evidence_float(evidence: list[str], key: str) -> float | None:
    raw_value = _evidence_value(evidence, key)
    if raw_value is None:
        return None
    try:
        return float(raw_value)
    except ValueError:
        return None


def _evidence_value(evidence: list[str], key: str) -> str | None:
    prefix = f"{key}:"
    for item in evidence:
        if item.startswith(prefix):
            return item[len(prefix) :].strip()
    return None


def _suppressible_issue_count(findings: list) -> int:
    return sum(
        _finding_occurrence_count(finding)
        for finding in findings
        if finding.finding_type == "issue" and bool(finding.row_indexes)
    )


def _finding_occurrence_count(finding) -> int:
    return len(finding.row_indexes) if finding.row_indexes else 1


def _issue_occurrence_count(findings: list) -> int:
    return sum(
        _finding_occurrence_count(finding)
        for finding in findings
        if finding.finding_type == "issue"
    )


def _finding_occurrence_breakdown(findings: list, label_attr: str) -> dict:
    counter: Counter[str] = Counter()
    for finding in findings:
        counter[getattr(finding, label_attr)] += _finding_occurrence_count(finding)
    return dict(counter)


def _build_quality_summary(
    state: PipelineState,
    *,
    findings: list,
    repairs: int,
    manual_review: int,
    suppressed_count: int,
) -> dict:
    data = pipeline_data(state)
    request = pipeline_request(state)
    dataset_meta = require_dataset_meta(state)
    return {
        "dataset_id": dataset_meta.dataset_id,
        "dataset_name": dataset_meta.dataset_name,
        "provider_name": dataset_meta.provider_name,
        "column_count": len(data.columns),
        "row_count": dataset_meta.total_rows,
        "repair_suggestion_count": repairs,
        "manual_review_count": manual_review,
        "finding_count": sum(_finding_occurrence_count(finding) for finding in findings),
        "manual_review_finding_count": sum(
            _finding_occurrence_count(finding)
            for finding in findings
            if finding.finding_type == "manual_review"
        ),
        "issue_finding_count": _issue_occurrence_count(findings),
        "suppressed_potential_finding_count": suppressed_count,
        "false_positive_policy": "deterministic_rule_or_count_mapped_or_strong_llm",
        "finding_breakdown": _finding_occurrence_breakdown(findings, "category_label"),
        "finding_type_breakdown": _finding_occurrence_breakdown(findings, "display_label"),
        "llm_agents_enabled": request.use_llm_agents,
    }
