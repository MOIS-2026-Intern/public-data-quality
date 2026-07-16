from __future__ import annotations

from collections import Counter

from backend.config.categorical import CATEGORICAL_LLM_CONFIDENCE_THRESHOLD
from backend.domain.policies.categorical import value_rows
from backend.domain.policies.categorical.column import (
    is_public_private_category_value,
    is_low_ratio_sido_spacing_variant,
    is_yn_value,
    looks_boolean_column,
    looks_free_text_column,
    looks_institution_category_column,
)
from backend.domain.policies.categorical.normalization import is_llm_normalization_actionable
from backend.domain.policies.categorical.text import clean_reason_text, is_specific_out_of_domain_reason
from backend.domain.policies.shared.findings import build_finding
from .llm_finding_support import (
    invalid_format_criterion_name as _invalid_format_criterion_name,
    invalid_format_message as _invalid_format_message,
    invalid_format_rule_id as _invalid_format_rule_id,
)


def apply_llm_categorical_findings(
    *,
    column,
    rows: list[dict[str, str]],
    result: dict,
    findings: list,
) -> int:
    counter = Counter(
        (row.get(column.raw_name) or "").strip()
        for row in rows
        if (row.get(column.raw_name) or "").strip()
    )
    if looks_free_text_column(column):
        return _append_out_of_domain_findings(
            column=column,
            rows=rows,
            result=result,
            findings=findings,
            counter=counter,
        )

    generated = 0
    generated += _append_normalization_findings(column=column, rows=rows, result=result, findings=findings, counter=counter)
    generated += _append_invalid_format_findings(column=column, rows=rows, result=result, findings=findings)
    generated += _append_out_of_domain_findings(column=column, rows=rows, result=result, findings=findings, counter=counter)
    return generated


def _append_normalization_findings(*, column, rows: list[dict[str, str]], result: dict, findings: list, counter: Counter[str]) -> int:
    generated = 0
    for item in result.get("normalizations", []):
        confidence = float(item.get("confidence") or 0.0)
        if confidence < CATEGORICAL_LLM_CONFIDENCE_THRESHOLD:
            continue
        source = str(item.get("source") or "").strip()
        target = str(item.get("target") or "").strip()
        reason = clean_reason_text(item.get("reason"))
        if is_low_ratio_sido_spacing_variant(column, source, counter):
            continue
        if not is_llm_normalization_actionable(column, source, target, reason):
            continue

        evidence = _llm_evidence(result, confidence, reason)
        if looks_boolean_column(column) and not is_yn_value(source) and is_yn_value(target):
            findings.append(
                build_finding(
                    column_name=column.raw_name,
                    severity="warning",
                    category_group="domain_validity",
                    criterion_name="boolean_domain",
                    rule_id="boolean_domain",
                    message=f"'{source}' 값은 Y/N 여부 컬럼의 허용값과 맞지 않을 수 있습니다.",
                    row_indexes=value_rows(rows, column.raw_name, source),
                    related_columns=[column.raw_name],
                    evidence=evidence,
                )
            )
            generated += 1
            continue

    return generated


def _append_invalid_format_findings(*, column, rows: list[dict[str, str]], result: dict, findings: list) -> int:
    generated = 0
    for item in result.get("invalid_format_values", []):
        confidence = float(item.get("confidence") or 0.0)
        if confidence < CATEGORICAL_LLM_CONFIDENCE_THRESHOLD:
            continue
        value = str(item.get("value") or "").strip()
        issue_type = str(item.get("issue_type") or "").strip()
        reason = clean_reason_text(item.get("reason"))
        if not value:
            continue
        if issue_type == "truncated_text":
            continue
        rule_id = _invalid_format_rule_id(issue_type)
        criterion_name = _invalid_format_criterion_name(issue_type)
        category_group = "completeness" if issue_type == "malformed_text" else "domain_validity"
        evidence = _llm_evidence(result, confidence, reason, f"issue_type:{issue_type}")
        findings.append(
            build_finding(
                column_name=column.raw_name,
                severity="warning",
                category_group=category_group,
                criterion_name=criterion_name,
                rule_id=rule_id,
                message=_invalid_format_message(value, issue_type),
                row_indexes=value_rows(rows, column.raw_name, value),
                related_columns=[column.raw_name],
                evidence=evidence,
            )
        )
        generated += 1
    return generated


def _append_out_of_domain_findings(*, column, rows: list[dict[str, str]], result: dict, findings: list, counter: Counter[str]) -> int:
    generated = 0
    for item in result.get("out_of_domain_values", []):
        confidence = float(item.get("confidence") or 0.0)
        if confidence < CATEGORICAL_LLM_CONFIDENCE_THRESHOLD:
            continue
        value = str(item.get("value") or "").strip()
        reason = clean_reason_text(item.get("reason"))
        if is_low_ratio_sido_spacing_variant(column, value, counter):
            continue
        if looks_institution_category_column(column) and is_public_private_category_value(value):
            continue
        if not value or not is_specific_out_of_domain_reason(reason):
            continue
        findings.append(
            build_finding(
                column_name=column.raw_name,
                severity="warning",
                category_group="domain_validity",
                criterion_name="categorical_semantic_domain",
                rule_id="categorical_value_out_of_domain",
                message=f"'{value}' 값은 해당 컬럼의 의미 도메인과 맞지 않을 수 있습니다.",
                row_indexes=value_rows(rows, column.raw_name, value),
                related_columns=[column.raw_name],
                evidence=_llm_evidence(result, confidence, reason),
            )
        )
        generated += 1
    return generated


def _llm_evidence(result: dict, confidence: float, reason: str, *extra: str) -> list[str]:
    evidence = [
        f"domain:{result.get('domain_label', '')}",
        f"confidence:{confidence:.2f}",
        f"model:{result.get('_llm_model', '')}",
        f"stage:{result.get('_llm_stage', '')}",
        f"escalated:{bool(result.get('_llm_escalated'))}",
        "detector:llm_categorical",
        *extra,
    ]
    if reason:
        evidence.append(f"reason:{reason}")
    return evidence
