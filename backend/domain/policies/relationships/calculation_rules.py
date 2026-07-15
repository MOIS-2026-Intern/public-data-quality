from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from backend.config.relationships import (
    CALCULATION_MATCH_TOLERANCE,
    CALCULATION_MISMATCH_RATIO_THRESHOLD,
    CALCULATION_SUM_TOTAL_NAME_TOKENS,
)
from backend.domain.entities.models import ColumnProfile, ValidationFinding
from ..columns import looks_numeric_column
from ..shared.findings import build_finding
from ..shared.parsing import parse_number
from .common import candidate_groups, is_related_numeric_pair


def looks_sum_total_column_name(name: str) -> bool:
    compact = "".join(str(name or "").split())
    return any(token in compact for token in CALCULATION_SUM_TOTAL_NAME_TOKENS)


def row_total_matches_components(
    row: Mapping[str, str],
    total_column_name: str,
    component_column_names: Sequence[str],
    *,
    tolerance: float = CALCULATION_MATCH_TOLERANCE,
) -> bool | None:
    component_names = [
        name
        for name in dict.fromkeys(str(name or "").strip() for name in component_column_names)
        if name and name != total_column_name
    ]
    if len(component_names) < 2:
        return None

    total_value = parse_number(str(row.get(total_column_name, "") or ""))
    if total_value is None:
        return None

    component_sum = 0.0
    for name in component_names:
        component_value = parse_number(str(row.get(name, "") or ""))
        if component_value is None:
            return None
        component_sum += component_value

    return abs(total_value - component_sum) <= tolerance


def validate_calculation_relationships(
    columns: list[ColumnProfile],
    rows: list[dict[str, str]],
    relationship_candidates: list[dict[str, Any]] | None = None,
) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    selected_groups = candidate_groups(relationship_candidates, {"calculation_formula"}, columns)
    if relationship_candidates is not None:
        groups = [(group[0], group[1:]) for group in selected_groups if len(group) >= 3]
    else:
        total_columns = [column for column in columns if "총" in column.normalized_name and looks_numeric_column(column)]
        part_columns = [column for column in columns if looks_numeric_column(column)]
        groups = [
            (
                total_col,
                [
                    column
                    for column in part_columns
                    if column.raw_name != total_col.raw_name and is_related_numeric_pair(total_col, column)
                ],
            )
            for total_col in total_columns
        ]

    for total_col, siblings in groups:
        if len(siblings) < 2:
            continue
        component_names = [column.raw_name for column in siblings]
        mismatch = 0
        comparable = 0
        mismatch_row_indexes: list[int] = []
        for row_index, row in enumerate(rows, start=1):
            matches = row_total_matches_components(
                row,
                total_col.raw_name,
                component_names,
            )
            if matches is None:
                continue
            comparable += 1
            if not matches:
                mismatch += 1
                mismatch_row_indexes.append(row_index)

        if (
            comparable
            and mismatch
            and mismatch / comparable >= CALCULATION_MISMATCH_RATIO_THRESHOLD
        ):
            findings.append(
                build_finding(
                    column_name=total_col.raw_name,
                    severity="warning",
                    category_group="relation_consistency",
                    criterion_name="calculation_formula",
                    message=(
                        f"'{total_col.raw_name}'가 "
                        f"'{ ' + '.join(component_names) }'와 일치하지 않는 행이 {mismatch}건 존재합니다."
                    ),
                    row_indexes=mismatch_row_indexes,
                    related_columns=[total_col.raw_name, *component_names],
                    evidence=[f"checked_rows:{comparable}", f"mismatch_rows:{mismatch}"],
                )
            )
    return findings
