from __future__ import annotations

from backend.domain.policies.shared.settings import (
    LLM_SEMANTIC_PROFILE_ALWAYS_TRIGGER_TAGS,
    LLM_SEMANTIC_PROFILE_AMBIGUOUS_TERMS,
    LLM_SEMANTIC_PROFILE_SKIP_TAGS,
)

LLM_FAST_MODEL = "gpt-4o-mini"
LLM_STRONG_MODEL = "gpt-4o"
LLM_DEFAULT_MODEL = LLM_FAST_MODEL
OPENAI_DEFAULT_API_URL = "https://api.openai.com/v1/chat/completions"
LLM_REQUEST_TIMEOUT_SECONDS = 120
LLM_RESOLUTION_CONFIDENCE = 0.78
LLM_STRONG_FALLBACK_CONFIDENCE = 0.72
LLM_SEMANTIC_PROFILE_ALWAYS_TRIGGER_NAME_TOKENS = {
    "주소",
    "소재지",
    "위치",
    "설명",
    "내용",
    "비고",
    "사유",
    "메모",
    "상세",
    "특이사항",
    "조치",
    "민원",
    "안내",
}
LLM_SEMANTIC_PROFILE_CONFIDENCE_DEFAULT = 0.75
