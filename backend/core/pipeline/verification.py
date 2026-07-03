from __future__ import annotations

import json
from collections import Counter

from ..schema.models import PipelineState
from .tracing import pipeline_trace

VERIFICATION_STEP_NAME = "verifier"

STRICT_ISSUE_RULE_IDS = {
    "garbled_text",
    "whitespace_issue",
    "special_character_issue",
    "date_domain",
    "boolean_domain",
    "number_domain",
    "amount_domain",
    "quantity_domain",
    "rate_domain",
    "time_sequence_consistency",
    "precedence_accuracy",
    "logical_consistency",
    "calculation_formula",
    "reference_relation",
    "address_region_prefix_mismatch",
}


def verify_results(state: PipelineState) -> PipelineState:
    repairs = 0
    manual_review = 0
    traces = list(state.get("agent_traces", []))
    findings = _strict_issue_findings(state.get("findings", []))

    for column in state["columns"]:
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
    )
    traces.append(
        pipeline_trace(
            VERIFICATION_STEP_NAME,
            action="verify_results",
            target=state["dataset_meta"].dataset_id,
            detail=json.dumps(summary, ensure_ascii=False),
        )
    )
    return {"summary": summary, "columns": state["columns"], "findings": findings, "agent_traces": traces}


def _strict_issue_findings(findings: list) -> list:
    return [
        finding
        for finding in findings
        if finding.finding_type == "issue"
        and bool(finding.row_indexes)
        and finding.rule_id in STRICT_ISSUE_RULE_IDS
    ]


def _build_quality_summary(
    state: PipelineState,
    *,
    findings: list,
    repairs: int,
    manual_review: int,
) -> dict:
    return {
        "dataset_id": state["dataset_meta"].dataset_id,
        "dataset_name": state["dataset_meta"].dataset_name,
        "provider_name": state["dataset_meta"].provider_name,
        "column_count": len(state["columns"]),
        "row_count": state["dataset_meta"].total_rows,
        "repair_suggestion_count": repairs,
        "manual_review_count": manual_review,
        "finding_count": len(findings),
        "manual_review_finding_count": sum(
            1 for finding in findings if finding.finding_type == "manual_review"
        ),
        "issue_finding_count": sum(1 for finding in findings if finding.finding_type == "issue"),
        "finding_breakdown": dict(Counter(finding.category_label for finding in findings)),
        "finding_type_breakdown": dict(Counter(finding.display_label for finding in findings)),
        "llm_agents_enabled": bool(state.get("use_llm_agents")),
    }
