from __future__ import annotations

NUMERIC_PAIR_BASE_STEM_TOKENS = ("총", "합계", "전체", "수", "개수", "건수", "금액", "비율", "율")
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
    "NUMERIC_PAIR_BASE_STEM_TOKENS",
    "REFERENCE_PAIR_TOKENS",
    "TIME_ORDER_TOKENS",
]
