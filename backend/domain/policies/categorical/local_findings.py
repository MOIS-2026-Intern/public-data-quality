from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from backend.domain.policies.helpers import build_finding
from .column import (
    allows_compact_domain_variant_detection,
    allows_context_free_replacement_detection,
    allows_institution_suffix_truncation,
    allows_local_prefix_truncation,
    allows_local_surface_normalization,
    looks_free_text_column,
    looks_name_column,
)
from .normalization import (
    canonical_normalization_key,
    find_compact_domain_variant_pairs,
    find_surface_normalization_pairs,
)
from .text import (
    looks_context_free_replacement_value,
    looks_malformed_text_value,
    looks_non_name_value,
    normalized_text,
)
from .truncation import (
    find_institution_suffix_completion_pairs,
    find_truncated_value_pairs,
    is_institution_suffix_completion,
    is_single_char_entity_completion,
)


def finding_key(finding) -> tuple[str, str, str, tuple[int, ...]]:
    return (
        finding.column_name,
        finding.rule_id,
        finding.message,
        tuple(finding.row_indexes),
    )


def value_rows(rows: list[dict[str, str]], column_name: str, target_value: str) -> list[int]:
    indexes: list[int] = []
    for row_index, row in enumerate(rows, start=1):
        value = (row.get(column_name) or "").strip()
        if value == target_value:
            indexes.append(row_index)
    return indexes


@dataclass(frozen=True)
class LocalCategoricalFindingCounts:
    normalization_count: int = 0
    truncated_count: int = 0
    malformed_count: int = 0
    non_name_count: int = 0
    domain_variant_count: int = 0
    context_free_replacement_count: int = 0

    @property
    def has_findings(self) -> bool:
        return bool(
            self.normalization_count
            or self.truncated_count
            or self.malformed_count
            or self.non_name_count
            or self.domain_variant_count
            or self.context_free_replacement_count
        )

    def trace_detail(self, skipped_reason: str) -> str:
        return (
            f"local_normalization_findings={self.normalization_count}, "
            f"local_truncated_findings={self.truncated_count}, "
            f"local_malformed_findings={self.malformed_count}, "
            f"local_non_name_findings={self.non_name_count}, "
            f"local_domain_variant_findings={self.domain_variant_count}, "
            f"local_context_free_replacement_findings={self.context_free_replacement_count}, "
            f"skipped:{skipped_reason}"
        )


def apply_local_categorical_findings(
    *,
    column,
    rows: list[dict[str, str]],
    counter: Counter[str],
    findings: list,
) -> LocalCategoricalFindingCounts:
    existing_finding_keys = {finding_key(finding) for finding in findings}
    if looks_free_text_column(column):
        return LocalCategoricalFindingCounts()

    normalization_pairs = (
        find_surface_normalization_pairs(counter)
        if allows_local_surface_normalization(column)
        else []
    )
    for source, target in normalization_pairs:
        finding = build_finding(
            column_name=column.raw_name,
            severity="warning",
            category_group="domain_validity",
            criterion_name="categorical_semantic_domain",
            rule_id="categorical_value_normalization",
            message=f"'{source}' 값은 '{target}'로 표면 형식을 표준화하는 것이 적절합니다.",
            row_indexes=value_rows(rows, column.raw_name, source),
            related_columns=[column.raw_name],
            evidence=[f"canonical:{canonical_normalization_key(source)}", "detector:surface_normalization"],
        )
        key = finding_key(finding)
        if key not in existing_finding_keys:
            findings.append(finding)
            existing_finding_keys.add(key)

    domain_variant_pairs = (
        find_compact_domain_variant_pairs(counter)
        if allows_compact_domain_variant_detection(column, counter)
        else []
    )
    for source, target in domain_variant_pairs:
        finding = build_finding(
            column_name=column.raw_name,
            severity="warning",
            category_group="domain_validity",
            criterion_name="categorical_semantic_domain",
            rule_id="categorical_value_out_of_domain",
            message=(
                f"'{source}' 값은 대표값 '{target}'와 매우 유사하지만 표기가 달라 "
                "입력 오류 가능성이 있습니다."
            ),
            row_indexes=value_rows(rows, column.raw_name, source),
            related_columns=[column.raw_name],
            evidence=[f"matched_representative_value:{target}", "detector:compact_domain_variant"],
        )
        key = finding_key(finding)
        if key not in existing_finding_keys:
            findings.append(finding)
            existing_finding_keys.add(key)

    malformed_values = [] if looks_free_text_column(column) else [value for value in counter if looks_malformed_text_value(value)]
    for value in malformed_values:
        finding = build_finding(
            column_name=column.raw_name,
            severity="warning",
            category_group="completeness",
            criterion_name="garbled_text",
            rule_id="garbled_text",
            message=(
                f"'{value}' 값은 불필요한 기호 또는 깨진 텍스트가 포함된 것으로 보입니다."
            ),
            row_indexes=value_rows(rows, column.raw_name, value),
            related_columns=[column.raw_name],
            evidence=["detector:malformed_text"],
        )
        key = finding_key(finding)
        if key not in existing_finding_keys:
            findings.append(finding)
            existing_finding_keys.add(key)

    semantic_outlier_values: dict[str, str] = {}
    for value in counter:
        if looks_name_column(column) and looks_non_name_value(value):
            semantic_outlier_values[value] = "non_name_phrase"
        elif (
            allows_context_free_replacement_detection(column, counter)
            and looks_context_free_replacement_value(value)
        ):
            semantic_outlier_values[value] = "context_free_replacement"

    for value, detector in semantic_outlier_values.items():
        if detector == "non_name_phrase":
            message = f"'{value}' 값은 명칭 컬럼에 들어갈 기관/자원명 형식이 아닙니다."
        else:
            message = (
                f"'{value}' 값은 컬럼의 기존 값 체계와 무관한 안내문 또는 상태 문구로 보여 "
                "도메인 밖 값일 가능성이 있습니다."
            )
        finding = build_finding(
            column_name=column.raw_name,
            severity="warning",
            category_group="domain_validity",
            criterion_name="categorical_semantic_domain",
            rule_id="categorical_value_out_of_domain",
            message=message,
            row_indexes=value_rows(rows, column.raw_name, value),
            related_columns=[column.raw_name],
            evidence=[f"detector:{detector}"],
        )
        key = finding_key(finding)
        if key not in existing_finding_keys:
            findings.append(finding)
            existing_finding_keys.add(key)

    prefix_pairs = find_truncated_value_pairs(counter) if allows_local_prefix_truncation(column) else []
    institution_pairs = (
        find_institution_suffix_completion_pairs(counter)
        if allows_institution_suffix_truncation(column)
        else []
    )
    truncated_pairs = sorted(set(prefix_pairs + institution_pairs))
    for source, target in truncated_pairs:
        is_single_char_completion = is_single_char_entity_completion(
            normalized_text(source),
            normalized_text(target),
        )
        is_institution_completion = is_institution_suffix_completion(
            normalized_text(source),
            normalized_text(target),
        )
        evidence = [
            f"matched_full_value:{target}",
            f"truncated_count:{counter[source]}",
            f"full_count:{counter[target]}",
            "mapping:one_to_one",
            "detector:prefix_truncation",
        ]
        if is_single_char_completion:
            evidence.append("mapping:single_char_entity_completion")
        if is_institution_completion:
            evidence.append("mapping:institution_suffix_completion")
        finding = build_finding(
            column_name=column.raw_name,
            severity="warning",
            category_group="domain_validity",
            criterion_name="categorical_semantic_domain",
            rule_id="categorical_value_truncated",
            message=(
                f"'{source}' 값은 '{target}' 값의 앞부분과 일치해 "
                "입력 중 잘림 가능성이 있습니다."
            ),
            row_indexes=value_rows(rows, column.raw_name, source),
            related_columns=[column.raw_name],
            evidence=evidence,
        )
        key = finding_key(finding)
        if key not in existing_finding_keys:
            findings.append(finding)
            existing_finding_keys.add(key)

    return LocalCategoricalFindingCounts(
        normalization_count=len(normalization_pairs),
        truncated_count=len(truncated_pairs),
        malformed_count=len(malformed_values),
        non_name_count=sum(1 for detector in semantic_outlier_values.values() if detector == "non_name_phrase"),
        domain_variant_count=len(domain_variant_pairs),
        context_free_replacement_count=sum(
            1 for detector in semantic_outlier_values.values() if detector == "context_free_replacement"
        ),
    )
