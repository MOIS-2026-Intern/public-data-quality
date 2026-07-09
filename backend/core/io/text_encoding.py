from __future__ import annotations


TEXT_DATASET_ENCODINGS = ("utf-8-sig", "utf-8", "cp949", "euc-kr", "utf-16-le", "utf-16-be")
_TEXT_ENCODING_BOMS = (
    (b"\xef\xbb\xbf", "utf-8-sig"),
    (b"\xff\xfe", "utf-16"),
    (b"\xfe\xff", "utf-16"),
)


def detect_text_encoding(payload: bytes, *, error_message: str) -> str:
    for bom, encoding in _TEXT_ENCODING_BOMS:
        if payload.startswith(bom):
            return encoding

    candidates: list[tuple[float, int, str]] = []
    for index, encoding in enumerate(TEXT_DATASET_ENCODINGS):
        try:
            text = payload.decode(encoding)
        except UnicodeError:
            continue
        candidates.append((_decoded_text_score(text), -index, encoding))

    if not candidates:
        raise ValueError(error_message)
    return max(candidates)[2]


def _decoded_text_score(text: str) -> float:
    if not text:
        return 0

    korean_count = sum(1 for char in text if "\uac00" <= char <= "\ud7a3")
    delimiter_count = sum(text.count(delimiter) for delimiter in (",", "\t", ";", "|"))
    newline_count = text.count("\n") + text.count("\r")
    nul_count = text.count("\x00")
    control_count = sum(1 for char in text if ord(char) < 32 and char not in "\r\n\t")
    printable_ascii_count = sum(1 for char in text if 32 <= ord(char) <= 126)

    score = 0.0
    score += min(korean_count, 2000) * 4
    score += min(delimiter_count, 500) * 2
    score += min(newline_count, 500)
    score += min(printable_ascii_count, 2000) * 0.05
    score -= nul_count * 30
    score -= control_count * 20
    return score
