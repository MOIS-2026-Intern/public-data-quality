from __future__ import annotations

LLM_SEMANTIC_PROFILE_ALWAYS_TRIGGER_TAGS = {"address"}
LLM_SEMANTIC_PROFILE_SKIP_TAGS = {
    "date",
    "phone",
    "geo_lat",
    "geo_lon",
    "coordinate_pair",
    "boolean",
    "amount",
    "quantity",
    "count",
    "rate",
    "width",
}
LLM_SEMANTIC_PROFILE_AMBIGUOUS_TERMS = {
    "구분",
    "상태",
    "코드",
    "번호",
    "명",
    "명칭",
    "값",
    "내용",
    "유형",
    "종류",
    "정보",
    "데이터",
}

LLM_FAST_MODEL = "openai/gpt-5-nano"
LLM_STRONG_MODEL = "openai/gpt-5-mini"
LLM_DEFAULT_MODEL = LLM_FAST_MODEL
OPENAI_DEFAULT_API_URL = "https://api.bizrouter.ai/v1/chat/completions"
LLM_REQUEST_TIMEOUT_SECONDS = 120
LLM_RESOLUTION_CONFIDENCE = 0.78
LLM_STRONG_FALLBACK_CONFIDENCE = 0.72
LLM_ROUTING_LOCAL_CONFIDENCE = 0.86
LLM_PROMPT_SAMPLE_VALUES_LIMIT = 3
LLM_PROMPT_TOP_VALUES_LIMIT = 5
LLM_PROMPT_VALUE_LENGTH_LIMIT = 80
LLM_CACHE_MAX_ENTRIES = 512
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
