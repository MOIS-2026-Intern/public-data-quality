from __future__ import annotations

from dataclasses import dataclass, field, fields, replace
from typing import Any, Literal


def _dump_value(value: Any) -> Any:
    if hasattr(value, "model_dump") and callable(value.model_dump):
        return value.model_dump()
    if isinstance(value, dict):
        return {key: _dump_value(nested_value) for key, nested_value in value.items()}
    if isinstance(value, list):
        return [_dump_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_dump_value(item) for item in value)
    return value


class _DomainModel:
    def _excluded_fields(self) -> set[str]:
        return set()

    def model_dump(self, *, exclude: set[str] | None = None) -> dict[str, Any]:
        excluded = self._excluded_fields().union(exclude or set())
        return {
            item.name: _dump_value(getattr(self, item.name))
            for item in fields(self)
            if item.name not in excluded
        }

    def model_copy(self, *, update: dict[str, Any] | None = None):
        return replace(self, **(update or {}))


@dataclass
class DatasetMeta(_DomainModel):
    dataset_id: str
    dataset_name: str
    keywords: list[str] = field(default_factory=list)
    provider_name: str = ""
    provider_code: str = ""
    dataset_type: str = ""
    service_type: str = ""
    data_format: str = ""
    request_fields: list[str] = field(default_factory=list)
    response_fields: list[str] = field(default_factory=list)
    update_cycle: str = ""
    total_rows: int | None = None


@dataclass
class ColumnProfile(_DomainModel):
    raw_name: str
    normalized_name: str
    source: Literal["request", "response"]
    unit: str | None = None
    tokens: list[str] = field(default_factory=list)
    semantic_tags: list[str] = field(default_factory=list)
    format_kind: Literal["fixed_format", "free_format"] | None = None
    standard_candidates: list[str] = field(default_factory=list)
    standard_match_type: str | None = None
    routing_confidence: float = 0.0
    assigned_rules: list[str] = field(default_factory=list)
    rag_required: bool = False
    rag_evidence: list[str] = field(default_factory=list)
    total_count: int | None = None
    non_empty_count: int = 0
    null_count: int = 0
    null_ratio: float | None = None
    distinct_count: int | None = None
    sample_values: list[str] = field(default_factory=list)
    top_values: list[tuple[str, int]] = field(default_factory=list)
    inferred_primitive_type: str | None = None
    numeric_parse_ratio: float | None = None
    date_parse_ratio: float | None = None
    numeric_min: float | None = None
    numeric_max: float | None = None
    numeric_mean: float | None = None
    semantic_profile_label: str | None = None
    semantic_profile_description: str | None = None
    semantic_profile_confidence: float | None = None
    semantic_profile_llm_needed: bool | None = None
    semantic_profile_llm_reasons: list[str] = field(default_factory=list)
    repair_suggestion: str | None = None
    verification_notes: list[str] = field(default_factory=list)

    def _excluded_fields(self) -> set[str]:
        return {
            "standard_candidates",
            "standard_match_type",
            "rag_required",
            "rag_evidence",
        }


@dataclass
class ValidationFinding(_DomainModel):
    column_name: str
    severity: Literal["info", "warning", "error"]
    finding_type: Literal["manual_review", "issue"]
    display_label: str
    category_group: str
    category_label: str
    criterion_name: str
    rule_id: str
    message: str
    criterion_description: str = ""
    llm_final_verification: str = ""
    row_indexes: list[int] = field(default_factory=list)
    related_columns: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
