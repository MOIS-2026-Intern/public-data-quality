from __future__ import annotations

NUMERIC_PAIR_BASE_STEM_TOKENS = ("총", "합계", "전체", "수", "개수", "건수", "금액", "비율", "율")
CALCULATION_SUM_TOTAL_NAME_TOKENS = ("합계", "총")
CALCULATION_MATCH_TOLERANCE = 1e-6
CALCULATION_MISMATCH_RATIO_THRESHOLD = 0.3
REGION_COLUMN_NAME_TOKENS = ("시도", "광역", "지역", "도명", "소속센터")
REGION_SAMPLE_ROW_LIMIT = 200
REGION_LIKE_MIN_RATIO = 0.6
REGION_EXACT_VALUES = (
    "서울특별시",
    "부산광역시",
    "대구광역시",
    "인천광역시",
    "광주광역시",
    "대전광역시",
    "울산광역시",
    "세종특별자치시",
    "제주특별자치도",
)
REGION_GENERIC_VALUE_PATTERNS = (
    r"[가-힣]+도",
    r"[가-힣]+특별시",
    r"[가-힣]+광역시",
    r"[가-힣]+특별자치도",
    r"[가-힣]+특별자치시",
)
REGION_ADDRESS_NAME_TOKENS = ("주소", "소재지")
REGION_ADDRESS_EXCLUDED_NAME_TOKENS = ("상세",)
TIME_ORDER_TOKENS = (
    ("시작", "종료"),
    ("개시", "종료"),
    ("접수", "처리"),
    ("등록", "수정"),
    ("생성", "수정"),
    ("발생", "종료"),
    ("출발", "도착"),
)
REFERENCE_PAIR_TOKENS = (
    ("코드", "명"),
    ("코드", "이름"),
    ("아이디", "명"),
    ("아이디", "이름"),
    ("번호", "명"),
)

__all__ = [
    "CALCULATION_MATCH_TOLERANCE",
    "CALCULATION_MISMATCH_RATIO_THRESHOLD",
    "CALCULATION_SUM_TOTAL_NAME_TOKENS",
    "NUMERIC_PAIR_BASE_STEM_TOKENS",
    "REFERENCE_PAIR_TOKENS",
    "REGION_ADDRESS_EXCLUDED_NAME_TOKENS",
    "REGION_ADDRESS_NAME_TOKENS",
    "REGION_COLUMN_NAME_TOKENS",
    "REGION_EXACT_VALUES",
    "REGION_GENERIC_VALUE_PATTERNS",
    "REGION_LIKE_MIN_RATIO",
    "REGION_SAMPLE_ROW_LIMIT",
    "TIME_ORDER_TOKENS",
]
