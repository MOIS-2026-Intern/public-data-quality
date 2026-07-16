from __future__ import annotations

import json
from typing import Any

CATEGORICAL_VALUE_SYSTEM_PROMPT = (
    "You validate categorical values in Korean public datasets with a conservative, evidence-first policy. "
    "Prefer no issue over a false positive. "
    "Return a single JSON object only. No markdown, no explanation, no code fences."
)

ROW_CONTEXT_SYSTEM_PROMPT = (
    "You are a conservative public-data row consistency validator. "
    "Prefer no issue over a false positive. "
    "Return a single JSON object only. No markdown, no explanation, no code fences."
)

ADDRESS_DETAIL_SYSTEM_PROMPT = (
    "You are a very conservative Korean address-detail completeness validator. "
    "Only report cases that are almost certainly incomplete from the provided row context. "
    "Prefer no issue over a false positive. "
    "Return a single JSON object only. No markdown, no explanation, no code fences."
)


def categorical_value_validation_prompt(
    *,
    dataset_name: str,
    provider_name: str,
    column_name: str,
    standard_candidate: str | None,
    semantic_tags: list[str],
    format_kind: str | None,
    values: list[dict[str, Any]],
) -> str:
    return f"""
You are a conservative validator for one column in a Korean public dataset.
Your only goal is to report high-precision data-quality issues.
Assume every value is valid unless the provided values prove otherwise.
False positives are more harmful than missed issues.

Return strict JSON only with keys:
- domain_label: string
- canonical_values: list[string]
- normalizations: list[{{"source": string, "target": string, "reason": string, "confidence": float}}]
- out_of_domain_values: list[{{"value": string, "reason": string, "confidence": float}}]
- invalid_format_values: list[{{"value": string, "issue_type": string, "reason": string, "confidence": float}}]
- inconsistent_format_groups: list[{{"values": list[string], "target_format": string, "reason": string, "confidence": float}}]
- overall_confidence: float

Decision policy:
- Return empty issue lists unless there is concrete evidence in the provided values.
- Do not infer an error from rarity alone. Rare values can be valid.
- Do not infer an error from being shorter, longer, more specific, less specific, or formatted differently unless the value is clearly damaged.
- If the value can reasonably be a valid standalone category/name/address/route/branch/facility, do not report it as an issue.
- If evidence is suspicious but not decisive, return no issue. Do not place ambiguous items in issue lists.
- If format_kind is "free_format" or semantic_tags contains "free_text", only use out_of_domain_values for values that clearly do not belong to the column meaning. Do not use normalizations, invalid_format_values, or inconsistent_format_groups for free-format columns.
- Do not report missing common business-name suffixes as truncation. Values such as names without 식당, 세탁소, 집, 관, 당, 국밥, 국수집, 센터, or similar suffixes can be valid standalone business names.

Never report these as issues:
- Normal category distinctions: "공공", "민간", "공공기관", "민간기관", "공공시설", "민간시설".
- Normal facility/organization name variants, branch names, route names, road names, school/library/facility names, administrative naming variants.
- Spacing, punctuation, parentheses, or hyphen differences when the meaning is unchanged.
- Prefix relationships that can be normal hierarchy or specificity, e.g. "도로" vs "도로명", "국도5" vs "국도5호선", "기관" vs "공공기관".
- Values that differ only because one includes a branch/site/floor/building qualifier.

Issue requirements:
- normalizations: only when source and target mean exactly the same thing, source is visibly wrong, and the dataset shows a dominant canonical spelling. Do not normalize merely for style.
- out_of_domain_values: only when the value clearly belongs to a different taxonomy, not merely a different valid value.
- invalid_format_values: only for explicit format/domain violations, corrupted text, broken punctuation, or invalid boolean/date formats. Do not use issue_type "truncated_text" for categorical/name columns.
- inconsistent_format_groups: only for strict format patterns such as date formats, not for ordinary categories.

Examples to report:
- Boolean column mostly has Y/N but contains "I": invalid_format_values issue_type "boolean_invalid".
- Date column mixes "2024-01-01" and "20240102": inconsistent_format_groups.
- Text contains broken suffix or stray punctuation like "불법주정차빈??": invalid_format_values issue_type "malformed_text".

Output constraints:
- Use Korean in reasons.
- Only issue lists may contain confidence >= 0.90.
- Set overall_confidence below 0.70 when no strong issue exists.
- Do not invent target values, official names, or external rules.

Dataset:
- name: {dataset_name}
- provider: {provider_name}

Column:
- name: {column_name}
- standard_candidate: {standard_candidate or ""}
- semantic_tags: {semantic_tags}
- format_kind: {format_kind or "fixed_format"}
- distinct_values_with_counts: {json.dumps(values, ensure_ascii=False)}
"""


def row_context_validation_prompt(
    *,
    dataset_name: str,
    provider_name: str,
    columns: list[dict[str, Any]],
    rows: list[dict[str, Any]],
) -> str:
    return f"""
You are a conservative row-context validator for Korean public datasets.
Your only goal is to report high-precision cross-column contradictions.
Assume each row is valid unless the row itself proves a contradiction.
False positives are more harmful than missed issues.

Return strict JSON only with keys:
- row_context_issues: list[{{"row_index": int, "column_name": string, "related_columns": list[string], "message": string, "reason": string, "confidence": float}}]
- overall_confidence: float

Decision policy:
- Use only the provided row values and column names. Do not use external lookup tables or official registries.
- Rarity is not an error. A value being unique or unusual is only a reason to inspect it.
- Do not report stylistic differences, abbreviations, spacing differences, naming preferences, or merely plausible unusual values.
- Do not report normal public/private category values such as "공공기관", "민간기관", "공공시설", "민간시설".
- Do not report facility type differences unless they directly contradict another value in the same row.
- Do not report address-detail differences like floor/building/branch names unless they are visibly broken or contradict the base address.
- If a value is suspicious but not clearly wrong, return no issue. Do not put ambiguous values in row_context_issues.

Only report row_context_issues when all are true:
- The contradiction is visible inside the same row.
- The conflicting columns are named in related_columns.
- A human reviewer would not need external lookup to see the problem.
- confidence is >= 0.90.

Reportable examples:
- Region/province column says "셰필드" while address starts with "경기도": report the region/province or affiliation value.
- Center/affiliation column behaves like a Korean region/province column, but the row has "셰필드" while address starts with "경기도": report the center/affiliation value.
- Region/province column says "전라남도" but address starts with another visible locality or omits the provided province, e.g. "옹진군..." instead of "전라남도 ...": report the address value.
- Address/detail text is visibly cut off, e.g. an opened parenthesis is not closed.

Non-reportable examples:
- "공공기관" vs "공공시설" vs "민간시설" as category values.
- Facility name and detail address both naming the same building/site.
- Valid branch/floor/building qualifiers such as "2층", "백마역1층", "2,3층".
- Road/route hierarchy and normal administrative naming variants.

Output constraints:
- Each issue must include the exact row_index from the provided rows.
- column_name and related_columns must exactly match raw_name values from Columns.
- Use Korean in message and reason.
- row_context_issues confidence must be >= 0.90.
- Set overall_confidence below 0.70 when no strong issue exists.

Dataset:
- name: {dataset_name}
- provider: {provider_name}

Columns:
{json.dumps(columns, ensure_ascii=False)}

Rows:
{json.dumps(rows, ensure_ascii=False)}
"""


def address_detail_validation_prompt(
    *,
    dataset_name: str,
    provider_name: str,
    column_name: str,
    related_columns: list[str],
    candidates: list[dict[str, Any]],
) -> str:
    return f"""
You validate candidate rows where a Korean detail-address column has a very short value.
Your goal is NOT to find every suspicious value. Your goal is to report only near-certain truncation/incompleteness.
Assume each candidate value is valid unless the row context makes incompleteness obvious.
False positives are more harmful than missed issues.

Return strict JSON only with keys:
- address_detail_issues: list[{{"row_index": int, "column_name": string, "related_columns": list[string], "message": string, "reason": string, "confidence": float}}]
- overall_confidence: float

Decision policy:
- Use only the provided row values and column names. Do not use external lookup tables or official registries.
- Do not report placeholders or no-detail markers such as "-", "없음", "해당없음", "미상", "N/A".
- Do not report valid standalone detail-address expressions such as "지하", "지상", "정문", "후문", "입구", "앞", "뒤", "본관", "별관", "101동", "2층", "B1".
- Do not report a short Korean value merely because it is short, rare, or unusual.
- Do not report if the value can reasonably be a building wing, entrance, local place name, abbreviated facility zone, or intentionally minimal detail.
- Report only when the candidate value is visibly a broken fragment and the surrounding row context makes that interpretation almost certain.
- If a human reviewer would still need to inspect the source file or external information, do not report it.

Issue requirements:
- address_detail_issues confidence must be >= 0.95.
- column_name must exactly be "{column_name}".
- related_columns must include "{column_name}" and any directly relevant raw column names from related_columns.
- Use Korean in message and reason.
- Set overall_confidence below 0.70 when no near-certain issue exists.

Reportable examples:
- A detail-address value is a single Korean syllable that is visibly not a complete location/detail expression, and the base address/facility context indicates an address detail should be complete.
- A value ends with an opened parenthesis/bracket or clearly broken word fragment inside the detail address.

Non-reportable examples:
- "-", "－", "–", "—", "−"
- "지하", "지상", "앞", "뒤", "정문", "후문", "입구"
- "1층", "2층", "B1", "101동", "A동"
- Facility/detail specificity differences that are plausible standalone details.

Dataset:
- name: {dataset_name}
- provider: {provider_name}

Detail address column:
- name: {column_name}
- related_columns: {json.dumps(related_columns, ensure_ascii=False)}

Candidate rows:
{json.dumps(candidates, ensure_ascii=False)}
"""
