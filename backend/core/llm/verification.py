from __future__ import annotations

import json
from typing import Any

FINAL_FINDING_VERIFICATION_SYSTEM_PROMPT = (
    "You are a conservative final verifier for Korean public-data quality findings. "
    "Your job is to remove false positives. Prefer suppressing an issue over reporting a weak issue. "
    "All user-facing message and reason fields must be written in Korean. "
    "Return a single JSON object only. No markdown, no explanation, no code fences."
)


def final_finding_verification_prompt(
    *,
    dataset_name: str,
    provider_name: str,
    candidates: list[dict[str, Any]],
) -> str:
    return f"""
You are verifying already-detected data-quality issue candidates before the user sees them.
For each candidate, decide whether the issue should be kept.
Use only the supplied column names, row values, original detector message, and evidence.
Do not use external registries or assumptions.
False positives are more harmful than missed issues.

Return strict JSON only with key:
- verified_findings: list[{{"id": string, "keep": boolean, "reason": string, "confidence": float, "message": string}}]

Decision policy:
- keep=true only when the supplied evidence and row values make the issue clear and defensible.
- keep=false when the value can reasonably be valid, when context is insufficient, or when the detector reason is speculative.
- Rarity, shortness, prefix similarity, naming specificity, branch/floor/site qualifiers, punctuation style, or free-form wording are not enough.
- If evidence contains mapping:institution_suffix_completion with matched_full_value, treat pairs such as 초등->초등학교, 유치->유치원, 어린이->어린이집 as a clear institution-type truncation unless the row context contradicts it.
- For free-text columns such as 기타사항, 내용, 설명, 비고, 서비스URL, 사이트, 대표문의, keep=true only for visibly corrupted, malformed, contradictory, or clearly truncated values.
- For date/boolean/numeric/domain format issues, keep=true only when the invalidity is explicit from the value and column meaning.
- For amount_domain candidates, do not keep an issue merely because the value is not a pure number. Suppress plausible price expressions such as currency units, comma formatting, open or closed ranges, multiple prices, parenthesized options/weights/platform prices, free/paid/inquiry/negotiated prices, and menu/item deleted or unavailable status values.
- For amount_domain candidates, keep=true only when the value is clearly unrelated to price, fee, availability, or menu/item status, or when it is visibly corrupted.
- For relationship issues, keep=true only when the contradiction is visible inside the provided row context.
- If keep=true, reason must explain the specific observed error and why it is not a normal valid variation.
- If keep=false, reason must explain why the candidate is ambiguous or plausibly valid.
- confidence must be >= 0.90 for keep=true and below 0.90 for keep=false.
- message must be a concise Korean user-facing error message when keep=true. It may be empty when keep=false.
- reason and message must be Korean. Do not use English in user-facing fields.

Dataset:
- name: {dataset_name}
- provider: {provider_name}

Candidates:
{json.dumps(candidates, ensure_ascii=False)}
"""
