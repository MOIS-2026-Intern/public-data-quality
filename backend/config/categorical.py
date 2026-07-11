from __future__ import annotations

CATEGORICAL_LLM_MIN_DISTINCT = 2
CATEGORICAL_LLM_MAX_DISTINCT = 30
CATEGORICAL_LLM_MIN_REPEAT_COUNT = 2
CATEGORICAL_LLM_CONFIDENCE_THRESHOLD = 0.9
ADDRESS_DETAIL_LLM_CONFIDENCE_THRESHOLD = 0.95
ADDRESS_DETAIL_LLM_MAX_CANDIDATES = 40

CATEGORICAL_NAME_TOKENS = (
    "구분",
    "유형",
    "종류",
    "상태",
    "여부",
    "유무",
    "급",
    "분류",
    "코드",
    "명칭",
    "일자",
    "일시",
    "날짜",
    "년월",
    "내용",
    "설명",
    "사유",
    "비고",
    "메모",
    "특이사항",
    "조치",
    "민원",
    "안내",
    "기타",
    "사이트",
    "대표문의",
    "서비스URL",
)
CATEGORICAL_SEMANTIC_TAGS = {"enum", "code", "boolean", "name", "date"}

ROW_CONTEXT_USEFUL_TOKENS = (
    "지역",
    "시도",
    "주소",
    "우편",
    "시설",
    "기관",
    "센터",
    "소속",
    "명",
    "구분",
    "분류",
    "인원",
    "정원",
    "수용",
)
ROW_CONTEXT_PRIORITY_TAGS = {
    "address",
    "name",
    "enum",
    "quantity",
    "count",
}
ROW_CONTEXT_SIGNAL_TOKENS = ("지역", "시도", "광역", "센터", "소속", "구분", "분류", "유형", "관리청")
ROW_CONTEXT_REGION_TOKENS = ("지역", "시도", "광역")
ROW_CONTEXT_ORGANIZATION_TOKENS = ("센터", "소속")
ROW_CONTEXT_CATEGORY_TOKENS = ("구분", "분류", "유형")
ROW_CONTEXT_MAX_COLUMNS = 20
ROW_CONTEXT_DEFAULT_LIMIT = 80
ROW_CONTEXT_EARLY_SAMPLE_LIMIT = 30
ROW_CONTEXT_SIGNAL_COUNT_LIMIT = 2
ROW_CONTEXT_UNIQUE_VALUE_COUNT = 1
ROW_CONTEXT_RARE_VALUE_COUNT = 2
ROW_CONTEXT_SIGNAL_SCORES = {
    "region": {ROW_CONTEXT_UNIQUE_VALUE_COUNT: 100, ROW_CONTEXT_RARE_VALUE_COUNT: 80},
    "organization": {ROW_CONTEXT_UNIQUE_VALUE_COUNT: 90, ROW_CONTEXT_RARE_VALUE_COUNT: 70},
    "category": {ROW_CONTEXT_UNIQUE_VALUE_COUNT: 60, ROW_CONTEXT_RARE_VALUE_COUNT: 40},
    "default": {ROW_CONTEXT_UNIQUE_VALUE_COUNT: 30, ROW_CONTEXT_RARE_VALUE_COUNT: 20},
}
ROW_CONTEXT_EARLY_SAMPLE_REASON = "early sample row"
