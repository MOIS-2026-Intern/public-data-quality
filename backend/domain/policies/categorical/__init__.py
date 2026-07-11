"""Categorical validation policies and helpers."""

from .column import (
    allows_institution_suffix_truncation,
    allows_local_prefix_truncation,
    looks_free_text_column,
)
from .local_findings import (
    LocalCategoricalFindingCounts,
    apply_local_categorical_findings,
    finding_key,
    value_rows,
)

__all__ = [
    "LocalCategoricalFindingCounts",
    "allows_institution_suffix_truncation",
    "allows_local_prefix_truncation",
    "apply_local_categorical_findings",
    "finding_key",
    "looks_free_text_column",
    "value_rows",
]
