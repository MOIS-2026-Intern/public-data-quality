from __future__ import annotations

import os
import re
from typing import Any

try:
    from ...core.config.constants import LLM_FAST_MODEL, LLM_STRONG_MODEL
    from ...core.llm import ChatLLMClient
    from ...core.llm.verification import (
        FINAL_FINDING_VERIFICATION_SYSTEM_PROMPT,
        final_finding_verification_prompt,
    )
    from ...core.schema.models import PipelineState, ValidationFinding
except ImportError:  # pragma: no cover
    if (__package__ or "").split(".", 1)[0] != "agents":
        raise
    from core.config.constants import LLM_FAST_MODEL, LLM_STRONG_MODEL
    from core.llm import ChatLLMClient
    from core.llm.verification import (
        FINAL_FINDING_VERIFICATION_SYSTEM_PROMPT,
        final_finding_verification_prompt,
    )
    from core.schema.models import PipelineState, ValidationFinding

from .categorical.utils import parse_json_content
from ..base import BaseAgent

FINAL_VERIFICATION_CONFIDENCE_THRESHOLD = 0.90
MAX_FINAL_VERIFICATION_CANDIDATES = 80
MAX_FINAL_VERIFICATION_ROWS_PER_FINDING = 12
MAX_FINAL_VERIFICATION_VALUE_LENGTH = 160


class LLMFinalFindingVerifier:
    def __init__(
        self,
        model_name: str | None = None,
        fast_model_name: str | None = None,
        strong_model_name: str | None = None,
        api_key: str | None = None,
    ):
        self.fast_model_name = fast_model_name or os.getenv("OPENAI_FAST_MODEL") or os.getenv("OPENAI_MODEL") or LLM_FAST_MODEL
        self.strong_model_name = strong_model_name or os.getenv("OPENAI_STRONG_MODEL") or model_name or LLM_STRONG_MODEL
        self.model_name = self.strong_model_name or self.fast_model_name
        self._llm = ChatLLMClient(model_name=self.model_name, api_key=api_key)
        self.last_error = ""
        self.last_response_preview = ""
        self.last_model_name = self.model_name

    @property
    def enabled(self) -> bool:
        return self._llm.enabled

    def verify(
        self,
        *,
        dataset_name: str,
        provider_name: str,
        candidates: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        response = self._llm.invoke_json(
            final_finding_verification_prompt(
                dataset_name=dataset_name,
                provider_name=provider_name,
                candidates=candidates,
            ),
            system_prompt=FINAL_FINDING_VERIFICATION_SYSTEM_PROMPT,
        )
        self.last_error = self._llm.last_error
        self.last_response_preview = self._llm.last_response_preview
        self.last_model_name = self._llm.model_name
        if response is None:
            return None
        payload = parse_json_content(response.content)
        if payload is None:
            self.last_error = f"llm_parse_error:{response.content[:200]}"
            return None
        payload.setdefault("verified_findings", [])
        return payload


class FinalFindingVerificationAgent(BaseAgent):
    name = "final_finding_verifier"

    def __init__(self, verifier: LLMFinalFindingVerifier | None = None):
        self.verifier = verifier

    def run(self, state: PipelineState) -> PipelineState:
        traces = list(state.get("agent_traces", []))
        findings = list(state.get("findings", []))
        use_llm = bool(state.get("use_llm_agents")) and self.verifier is not None and self.verifier.enabled
        issue_pairs = [
            (index, finding)
            for index, finding in enumerate(findings)
            if finding.finding_type == "issue" and finding.row_indexes
        ]

        if not use_llm:
            traces.append(
                self.trace(
                    action="final_verify_findings",
                    detail=f"llm_disabled_or_unavailable; issue_findings={len(issue_pairs)}",
                )
            )
            return {"findings": findings, "agent_traces": traces}

        rows = state.get("validation_rows") or state.get("preview_rows", [])
        candidates = _finding_candidates(issue_pairs, rows)
        if not candidates:
            traces.append(self.trace(action="final_verify_findings", detail="issue_findings=0"))
            return {"findings": findings, "agent_traces": traces}

        limited_candidates = candidates[:MAX_FINAL_VERIFICATION_CANDIDATES]
        limited_candidate_ids = {str(candidate["id"]) for candidate in limited_candidates}
        payload = self.verifier.verify(
            dataset_name=state["dataset_meta"].dataset_name,
            provider_name=state["dataset_meta"].provider_name,
            candidates=limited_candidates,
        )
        if not payload:
            traces.append(
                self.trace(
                    action="final_verify_findings",
                    detail=(
                        f"llm_no_result; issue_findings={len(issue_pairs)}, "
                        f"model={self.verifier.last_model_name}, error={self.verifier.last_error}, "
                        f"preview={self.verifier.last_response_preview}"
                    ),
                )
            )
            return {"findings": findings, "agent_traces": traces}

        decisions = _verification_decisions(payload)
        verified_findings: list[ValidationFinding] = []
        suppressed = 0
        for index, finding in enumerate(findings):
            if finding.finding_type != "issue" or not finding.row_indexes:
                verified_findings.append(finding)
                continue

            if _is_protected_deterministic_issue(finding):
                verified_findings.append(_apply_protected_final_verification(finding))
                continue

            decision = decisions.get(f"f{index}")
            if decision is None:
                if f"f{index}" not in limited_candidate_ids:
                    verified_findings.append(finding)
                else:
                    suppressed += _occurrence_count(finding)
                continue

            if not _keeps_issue(decision):
                suppressed += _occurrence_count(finding)
                continue

            verified_findings.append(_apply_final_verification(finding, decision, self.verifier.last_model_name))

        traces.append(
            self.trace(
                action="final_verify_findings",
                detail=(
                    f"candidates={len(candidates)}, verified={len(verified_findings)}, "
                    f"suppressed_occurrences={suppressed}, model={self.verifier.last_model_name}"
                ),
            )
        )
        return {"findings": verified_findings, "agent_traces": traces}


def _finding_candidates(
    findings: list[tuple[int, ValidationFinding]],
    rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for index, finding in findings:
        candidates.append(
            {
                "id": f"f{index}",
                "column_name": finding.column_name,
                "rule_id": finding.rule_id,
                "severity": finding.severity,
                "category": finding.category_label,
                "criterion": finding.criterion_name,
                "message": finding.message,
                "related_columns": finding.related_columns,
                "evidence": finding.evidence,
                "sample_rows": _sample_finding_rows(finding, rows),
            }
        )
    return sorted(candidates, key=_candidate_priority)


def _candidate_priority(candidate: dict[str, Any]) -> tuple[int, str]:
    rule_id = str(candidate.get("rule_id") or "")
    if rule_id == "amount_domain":
        return (0, str(candidate.get("id") or ""))
    return (1, str(candidate.get("id") or ""))


def _sample_finding_rows(finding: ValidationFinding, rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    sample_rows: list[dict[str, Any]] = []
    columns = list(dict.fromkeys([finding.column_name, *finding.related_columns]))
    for row_index in finding.row_indexes[:MAX_FINAL_VERIFICATION_ROWS_PER_FINDING]:
        row = rows[row_index - 1] if 0 < row_index <= len(rows) else {}
        values = {
            column: _truncate_value(row.get(column, ""))
            for column in columns
            if column in row or column == finding.column_name
        }
        sample_rows.append({"row_index": row_index, "values": values})
    return sample_rows


def _truncate_value(value: object) -> str:
    text = str(value or "").strip()
    if len(text) <= MAX_FINAL_VERIFICATION_VALUE_LENGTH:
        return text
    return f"{text[:MAX_FINAL_VERIFICATION_VALUE_LENGTH]}..."


def _verification_decisions(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    decisions: dict[str, dict[str, Any]] = {}
    for item in payload.get("verified_findings") or []:
        if not isinstance(item, dict):
            continue
        finding_id = str(item.get("id") or "").strip()
        if finding_id:
            decisions[finding_id] = item
    return decisions


def _keeps_issue(decision: dict[str, Any]) -> bool:
    if decision.get("keep") is not True:
        return False
    return _confidence(decision.get("confidence")) >= FINAL_VERIFICATION_CONFIDENCE_THRESHOLD


def _is_protected_deterministic_issue(finding: ValidationFinding) -> bool:
    if finding.rule_id != "categorical_value_truncated":
        return False
    evidence = finding.evidence or []
    return (
        "detector:prefix_truncation" in evidence
        and "mapping:institution_suffix_completion" in evidence
        and any(item.startswith("matched_full_value:") for item in evidence)
    )


def _apply_protected_final_verification(finding: ValidationFinding) -> ValidationFinding:
    evidence = [*finding.evidence, "final_verifier:deterministic_institution_suffix"]
    return finding.model_copy(update={"evidence": list(dict.fromkeys(evidence))})


def _apply_final_verification(
    finding: ValidationFinding,
    decision: dict[str, Any],
    model_name: str,
) -> ValidationFinding:
    reason = _korean_text_or_empty(decision.get("reason"))
    evidence = [
        *finding.evidence,
        "final_verifier:llm",
        f"final_verifier_model:{model_name}",
        f"final_verifier_confidence:{_confidence(decision.get('confidence')):.2f}",
    ]
    if reason:
        evidence.append(f"final_verifier_reason:{reason}")
    return finding.model_copy(
        update={
            "llm_final_verification": reason,
            "evidence": evidence,
        }
    )


def _clean_text(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def _korean_text_or_empty(value: object) -> str:
    text = _clean_text(value)
    if not text:
        return ""
    return text if re.search(r"[가-힣]", text) else ""


def _confidence(value: object) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _occurrence_count(finding: ValidationFinding) -> int:
    return len(finding.row_indexes) if finding.row_indexes else 1
