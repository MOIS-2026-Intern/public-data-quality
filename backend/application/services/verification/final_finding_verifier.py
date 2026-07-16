from __future__ import annotations

import re
from typing import Any

from backend.application.shared import parse_json_content
from backend.config.verification import (
    FINAL_VERIFICATION_LOCAL_RULE_IDS,
    FINAL_VERIFICATION_CONFIDENCE_THRESHOLD,
    MAX_FINAL_VERIFICATION_CANDIDATES,
    MAX_FINAL_VERIFICATION_ROWS_PER_FINDING,
    MAX_FINAL_VERIFICATION_VALUE_LENGTH,
)
from backend.application.ports import JsonLLMPort
from backend.application.prompts.verification import (
    FINAL_FINDING_VERIFICATION_SYSTEM_PROMPT,
    final_finding_verification_prompt,
)
from backend.domain.entities.models import ValidationFinding


class LLMFinalFindingVerifier:
    def __init__(
        self,
        *,
        llm: JsonLLMPort | None = None,
    ):
        self._llm = llm
        self.model_name = getattr(llm, "model_name", "")
        self.last_error = ""
        self.last_response_preview = ""
        self.last_model_name = self.model_name

    @property
    def enabled(self) -> bool:
        return self._llm is not None and self._llm.enabled

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


def _skip_llm_final_verification(finding: ValidationFinding) -> bool:
    return _is_protected_deterministic_issue(finding) or _is_local_final_verification_issue(finding)


def _group_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], dict[str, Any]] = {}
    ordered_keys: list[tuple[Any, ...]] = []

    for candidate in candidates:
        key = _candidate_group_key(candidate)
        grouped_candidate = grouped.get(key)
        if grouped_candidate is None:
            grouped_candidate = {
                **candidate,
                "finding_ids": [str(candidate.get("id") or "")],
                "candidate_count": 1,
            }
            grouped[key] = grouped_candidate
            ordered_keys.append(key)
            continue

        grouped_candidate["finding_ids"].append(str(candidate.get("id") or ""))
        grouped_candidate["candidate_count"] = int(grouped_candidate.get("candidate_count") or 0) + 1
        grouped_candidate["sample_rows"] = _merge_group_sample_rows(
            grouped_candidate.get("sample_rows") or [],
            candidate.get("sample_rows") or [],
        )

    return [grouped[key] for key in ordered_keys]


def _candidate_priority(candidate: dict[str, Any]) -> tuple[int, str]:
    rule_id = str(candidate.get("rule_id") or "")
    if rule_id == "amount_domain":
        return (0, str(candidate.get("id") or ""))
    return (1, str(candidate.get("id") or ""))


def _candidate_group_key(candidate: dict[str, Any]) -> tuple[Any, ...]:
    return (
        str(candidate.get("column_name") or ""),
        str(candidate.get("rule_id") or ""),
        str(candidate.get("message") or ""),
        tuple(str(value).strip() for value in candidate.get("related_columns") or []),
        tuple(str(value).strip() for value in candidate.get("evidence") or []),
        tuple(_sample_row_signature(row) for row in candidate.get("sample_rows") or []),
    )


def _merge_group_sample_rows(existing_rows: list[dict[str, Any]], new_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged = list(existing_rows)
    seen_signatures = {_sample_row_signature(row) for row in merged}
    for row in new_rows:
        signature = _sample_row_signature(row)
        if signature in seen_signatures:
            continue
        merged.append(row)
        seen_signatures.add(signature)
    return merged[:MAX_FINAL_VERIFICATION_ROWS_PER_FINDING]


def _sample_row_signature(row: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    values = row.get("values") if isinstance(row, dict) else {}
    if not isinstance(values, dict):
        return ()
    return tuple(sorted((str(key), str(value)) for key, value in values.items()))


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


def _is_local_final_verification_issue(finding: ValidationFinding) -> bool:
    if finding.rule_id not in FINAL_VERIFICATION_LOCAL_RULE_IDS:
        return False
    evidence = finding.evidence or []
    return not any(item.startswith("detector:llm_") or item.startswith("stage:") for item in evidence)


def _apply_protected_final_verification(finding: ValidationFinding) -> ValidationFinding:
    evidence = [*finding.evidence, "final_verifier:deterministic_institution_suffix"]
    return finding.model_copy(update={"evidence": list(dict.fromkeys(evidence))})


def _apply_local_final_verification(finding: ValidationFinding) -> ValidationFinding:
    evidence = [*finding.evidence, "final_verifier:local_rule"]
    return finding.model_copy(
        update={
            "llm_final_verification": _local_final_verification_reason(finding.rule_id),
            "evidence": list(dict.fromkeys(evidence)),
        }
    )


def _local_final_verification_reason(rule_id: str) -> str:
    reasons = {
        "garbled_text": "로컬 규칙에서 깨진 문자 또는 비정상 텍스트가 확인되었습니다.",
        "whitespace_issue": "로컬 규칙에서 과도한 공백 또는 공백 불일치가 확인되었습니다.",
        "special_character_issue": "로컬 규칙에서 허용 범위를 벗어난 특수문자가 확인되었습니다.",
        "required_value": "로컬 규칙에서 필수성이 높은 컬럼의 결측값이 확인되었습니다.",
        "duplicate_data": "로컬 규칙에서 중복 식별자 값이 확인되었습니다.",
        "number_domain": "로컬 규칙에서 번호 또는 숫자 도메인 범위 오류가 확인되었습니다.",
        "boolean_domain": "로컬 규칙에서 여부 도메인의 허용값 범위 이탈이 확인되었습니다.",
        "quantity_domain": "로컬 규칙에서 수량 도메인의 숫자 파싱 또는 범위 오류가 확인되었습니다.",
        "rate_domain": "로컬 규칙에서 율 도메인의 허용 범위 이탈이 확인되었습니다.",
    }
    return reasons.get(rule_id, "로컬 규칙에서 확정 가능한 오류가 확인되었습니다.")


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
