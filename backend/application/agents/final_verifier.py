from __future__ import annotations

from backend.application.dto import (
    PipelineState,
    merge_state_updates,
    pipeline_data,
    pipeline_request,
    pipeline_result,
    pipeline_rows,
    require_dataset_meta,
    update_pipeline_result,
)
from backend.application.agents.base import BaseAgent
from backend.application.services.verification.final_finding_verifier import (
    LLMFinalFindingVerifier,
    MAX_FINAL_VERIFICATION_CANDIDATES,
    _apply_final_verification,
    _apply_protected_final_verification,
    _finding_candidates,
    _is_protected_deterministic_issue,
    _keeps_issue,
    _occurrence_count,
    _verification_decisions,
)
from backend.domain.entities.models import ValidationFinding


class FinalFindingVerificationAgent(BaseAgent):
    name = "final_finding_verifier"

    def __init__(self, verifier: LLMFinalFindingVerifier | None = None):
        self.verifier = verifier

    def run(self, state: PipelineState) -> PipelineState:
        request = pipeline_request(state)
        data = pipeline_data(state)
        result = pipeline_result(state)
        traces = list(result.agent_traces)
        findings = list(result.findings)
        use_llm = request.use_llm_agents and self.verifier is not None and self.verifier.enabled
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
            return update_pipeline_result(state, findings=findings, agent_traces=traces)

        rows = pipeline_rows(state)
        candidates = _finding_candidates(issue_pairs, rows)
        if not candidates:
            traces.append(self.trace(action="final_verify_findings", detail="issue_findings=0"))
            return update_pipeline_result(state, findings=findings, agent_traces=traces)

        limited_candidates = candidates[:MAX_FINAL_VERIFICATION_CANDIDATES]
        limited_candidate_ids = {str(candidate["id"]) for candidate in limited_candidates}
        dataset_meta = require_dataset_meta(state)
        payload = self.verifier.verify(
            dataset_name=dataset_meta.dataset_name,
            provider_name=dataset_meta.provider_name,
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
            return update_pipeline_result(state, findings=findings, agent_traces=traces)

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
        return update_pipeline_result(state, findings=verified_findings, agent_traces=traces)
