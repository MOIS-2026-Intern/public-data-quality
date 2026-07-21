from __future__ import annotations

CATEGORICAL_LLM_MIN_REPEAT_COUNT = 2
CATEGORICAL_LLM_MIN_DISTINCT = 2
CATEGORICAL_LLM_MAX_DISTINCT = 80
CATEGORICAL_LLM_MAX_DISTINCT_RATIO = 0.15
CATEGORICAL_LLM_MAX_VALUES = 40
CATEGORICAL_LLM_MAX_WORKERS = 4
CATEGORICAL_LLM_CONFIDENCE_THRESHOLD = 0.9
CATEGORICAL_LOW_RATIO_NORMAL_VALUE_MAX_RATIO = 0.05
CATEGORICAL_COMPACT_SET_MIN_TOTAL = 10
CATEGORICAL_COMPACT_SET_MAX_DISTINCT = 80
CATEGORICAL_COMPACT_SET_MAX_DISTINCT_RATIO = 0.1
CATEGORICAL_COMPACT_SET_MIN_TOP_RATIO = 0.2
ADDRESS_DETAIL_LLM_CONFIDENCE_THRESHOLD = 0.95
ADDRESS_DETAIL_LLM_MAX_CANDIDATES = 20
SIDO_COLUMN_NAMES = {"시도", "시도명", "광역시도", "광역시도명"}
KOREAN_SIDO_VARIANTS = {
    "서울",
    "부산",
    "대구",
    "인천",
    "광주",
    "대전",
    "울산",
    "세종",
    "세종시",
    "경기",
    "강원",
    "충북",
    "충남",
    "전북",
    "전남",
    "경북",
    "경남",
    "제주",
    "제주도",
    "서울특별시",
    "부산광역시",
    "대구광역시",
    "인천광역시",
    "광주광역시",
    "대전광역시",
    "울산광역시",
    "세종특별자치시",
    "경기도",
    "강원도",
    "충청북도",
    "충청남도",
    "전라북도",
    "전라남도",
    "경상북도",
    "경상남도",
    "제주특별자치도",
}

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
CATEGORICAL_SEMANTIC_TAGS = {"enum", "code", "name"}
CATEGORICAL_LLM_SKIP_TAGS = {
    "date",
    "boolean",
    "numeric",
    "amount",
    "quantity",
    "count",
    "rate",
    "width",
    "phone",
    "geo_lat",
    "geo_lon",
    "coordinate_pair",
    "identifier",
}

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
ROW_CONTEXT_MAX_COLUMNS = 12
ROW_CONTEXT_DEFAULT_LIMIT = 40
ROW_CONTEXT_EARLY_SAMPLE_LIMIT = 10
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
ROW_CONTEXT_SUM_MISMATCH_MARKERS = (
    "합계",
    "합산",
    "세부 항목",
    "세부항목",
    "일치하지",
    "불일치",
    "합이",
    "sum",
)

SHORT_KOREAN_PREFIX_LEN = 2
MIN_TRUNCATED_PREFIX_LEN = 3
MIN_TRUNCATED_PREFIX_RATIO = 0.25
ENTITY_COMPLETION_SUFFIXES = {
    "교",
    "원",
    "관",
    "소",
    "당",
    "집",
    "학교",
    "유치원",
    "어린이집",
    "병원",
    "의원",
    "약국",
    "학원",
    "센터",
    "회관",
    "복지관",
    "도서관",
    "보건소",
    "경로당",
    "관리소",
}
INSTITUTION_SUFFIX_COMPLETIONS = {
    "유치": "유치원",
    "초등": "초등학교",
    "초등학": "초등학교",
    "어린이": "어린이집",
}
INCOMPLETE_ENTITY_MODIFIER_SUFFIXES = {
    "국립",
    "공립",
    "사립",
    "시립",
    "도립",
    "군립",
    "구립",
    "공영",
    "시영",
    "도영",
    "군영",
    "구영",
    "공공",
    "민간",
    "광역",
    "지역",
}
COMPLETE_LOCATION_VALUES = {
    "정문",
    "후문",
    "입구",
    "교내",
    "본관",
    "별관",
    "강당",
    "운동장",
    "주차장",
    "앞",
    "뒤",
    "뒷편",
    "뒤편",
    "서편",
    "동편",
    "남편",
    "북편",
    "지상",
    "지하",
}
FACILITY_QUALIFIER_SUFFIXES = {
    "주차장",
    "명절주차장",
    "체육관주차장",
    "운동장주차장",
    "공영주차장",
}
CATEGORY_QUALIFIER_SUFFIXES = {
    "가칭",
    "미상",
    "불명",
    "예정",
    "의심",
    "잠정",
    "추정",
}
ORGANIZATION_BRANCH_SUFFIX_PATTERNS = (
    r"^[가-힣]+(?:특별자치도|특별자치시|광역시|특별시|자치도|도|시|군|구)(?:지부|지회|분회|본부|본점|지점|출장소|사무소)$",
    r"^(?:중앙|지역|권역|광역|전국|본부|본점|지점|지부|지회|분회|출장소|사무소)$",
)
STRUCTURED_DETAIL_EXACT_SUFFIXES = {
    "정문",
    "후문",
    "입구",
    "출입구",
    "앞",
    "뒤",
    "뒷편",
    "뒤편",
    "동편",
    "서편",
    "남편",
    "북편",
    "지상",
    "지하",
    "본관",
    "별관",
    "분관",
    "동관",
    "서관",
    "남관",
    "북관",
    "중앙관",
    "신관",
    "구관",
}
STRUCTURED_DETAIL_EXACT_SUFFIXES_BY_LENGTH = tuple(sorted(STRUCTURED_DETAIL_EXACT_SUFFIXES, key=len, reverse=True))
STRUCTURED_DETAIL_COMPONENT_PATTERNS = (
    r"^(?:지하|B)\d+층",
    r"^\d+(?:,\d+)*층",
    r"^\d+-\d+층",
    r"^\d+호실",
    r"^\d+호",
    r"^\d+실",
    r"^\d+동",
    r"^[A-Z]동",
    r"^\d+번출구",
    r"^\d+게이트",
    r"^[A-Z]게이트",
)
NAMED_DETAIL_PREFIX_PATTERNS = (r"^[가-힣A-Za-z0-9]+역",)
