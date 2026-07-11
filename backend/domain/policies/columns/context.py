from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from backend.domain.entities.models import ColumnProfile, ValidationFinding

Rows = list[dict[str, str]]


@dataclass(frozen=True)
class ColumnRuleContext:
    column: ColumnProfile
    rows: Rows
    sample_values: list[str]


ColumnRuleCheck = Callable[[ColumnRuleContext], list[ValidationFinding]]


def build_column_rule_context(
    column: ColumnProfile,
    rows: Rows,
) -> ColumnRuleContext:
    row_values = [row.get(column.raw_name) or "" for row in rows]
    sample_values = row_values if row_values else column.sample_values[:5]
    return ColumnRuleContext(
        column=column,
        rows=rows,
        sample_values=sample_values,
    )


def collect_findings(
    checks: tuple[ColumnRuleCheck, ...],
    context: ColumnRuleContext,
) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    for check in checks:
        findings.extend(check(context))
    return findings
