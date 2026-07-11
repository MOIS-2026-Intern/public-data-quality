from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.infrastructure.io.loaders import iter_uploaded_rows, load_uploaded_dataset_meta, load_uploaded_headers


def test_cp949_csv_headers_and_rows_are_loaded(tmp_path) -> None:
    path = tmp_path / "korean.csv"
    path.write_bytes("서비스명,주소\n유치원,서울\n초등학교,부산\n".encode("cp949"))

    assert load_uploaded_headers(path) == ["서비스명", "주소"]
    assert list(iter_uploaded_rows(path)) == [
        {"서비스명": "유치원", "주소": "서울"},
        {"서비스명": "초등학교", "주소": "부산"},
    ]


def test_cp949_csv_uploaded_meta_uses_detected_encoding(tmp_path) -> None:
    path = tmp_path / "korean.csv"
    path.write_bytes("서비스명,주소\n유치원,서울\n".encode("cp949"))

    meta = load_uploaded_dataset_meta(path)

    assert meta.response_fields == ["서비스명", "주소"]


def test_cp949_csv_with_ascii_prefix_is_loaded_from_full_file_detection(tmp_path) -> None:
    path = tmp_path / "late_korean.csv"
    ascii_rows = "name,address\n" + "".join(f"name{i},address{i}\n" for i in range(5000))
    path.write_bytes((ascii_rows + "유치원,서울\n").encode("cp949"))

    rows = list(iter_uploaded_rows(path))

    assert rows[-1] == {"name": "유치원", "address": "서울"}


def test_utf16le_csv_without_bom_is_loaded(tmp_path) -> None:
    path = tmp_path / "utf16le.csv"
    path.write_bytes("서비스명,주소\n유치원,서울\n".encode("utf-16-le"))

    assert load_uploaded_headers(path) == ["서비스명", "주소"]
    assert list(iter_uploaded_rows(path)) == [{"서비스명": "유치원", "주소": "서울"}]


def test_tab_delimited_csv_with_commas_in_text_is_not_split_by_comma(tmp_path) -> None:
    path = tmp_path / "petition.csv"
    path.write_text(
        "\n".join(
            [
                "제안이유\t공표청구개요\t시작일\t종료일\t대상자수\t서명수",
                (
                    "노동인권, 인권친화적 노동환경 등 개념이 정립되지 않은 내용"
                    "\t청구일 : 2019. 12. 10.(화)"
                    "\t2019-12-10\t2020-03-09\t670208\t6775"
                ),
                (
                    "대농과 기업농, 농촌, 농어업 관련 내용"
                    "\t청구일 : 2021. 1. 22.(금)"
                    "\t2021-01-25\t2021-07-24\t1528282\t15283"
                ),
            ]
        ),
        encoding="utf-8",
    )

    assert load_uploaded_headers(path) == ["제안이유", "공표청구개요", "시작일", "종료일", "대상자수", "서명수"]
    assert list(iter_uploaded_rows(path)) == [
        {
            "제안이유": "노동인권, 인권친화적 노동환경 등 개념이 정립되지 않은 내용",
            "공표청구개요": "청구일 : 2019. 12. 10.(화)",
            "시작일": "2019-12-10",
            "종료일": "2020-03-09",
            "대상자수": "670208",
            "서명수": "6775",
        },
        {
            "제안이유": "대농과 기업농, 농촌, 농어업 관련 내용",
            "공표청구개요": "청구일 : 2021. 1. 22.(금)",
            "시작일": "2021-01-25",
            "종료일": "2021-07-24",
            "대상자수": "1528282",
            "서명수": "15283",
        },
    ]


def test_unquoted_commas_are_repaired_by_right_anchored_columns(tmp_path) -> None:
    path = tmp_path / "broken_commas.csv"
    path.write_text(
        "\n".join(
            [
                "제안이유,공표청구개요,시작일,종료일,대상자수,서명수",
                (
                    "노동인권, 인권친화적 노동환경 등 개념이 정립되지 않은 내용"
                    ",청구일 : 2019. 12. 10.(화)"
                    ",2019-12-10,2020-03-09,670208,6775"
                ),
                (
                    "대농과 기업농, 농촌, 농어업 관련 내용"
                    ",청구일 : 2021. 1. 22.(금)"
                    ",2021-01-25,2021-07-24,1528282,15283"
                ),
            ]
        ),
        encoding="utf-8",
    )

    assert list(iter_uploaded_rows(path)) == [
        {
            "제안이유": "노동인권, 인권친화적 노동환경 등 개념이 정립되지 않은 내용",
            "공표청구개요": "청구일 : 2019. 12. 10.(화)",
            "시작일": "2019-12-10",
            "종료일": "2020-03-09",
            "대상자수": "670208",
            "서명수": "6775",
        },
        {
            "제안이유": "대농과 기업농, 농촌, 농어업 관련 내용",
            "공표청구개요": "청구일 : 2021. 1. 22.(금)",
            "시작일": "2021-01-25",
            "종료일": "2021-07-24",
            "대상자수": "1528282",
            "서명수": "15283",
        },
    ]


def test_unquoted_commas_preserve_left_anchor_before_free_text(tmp_path) -> None:
    path = tmp_path / "id_and_text.csv"
    path.write_text(
        "\n".join(
            [
                "목록키,제안이유,시작일,건수",
                "A-001,본문에, 쉼표가, 많음,2024-01-02,12",
            ]
        ),
        encoding="utf-8",
    )

    assert list(iter_uploaded_rows(path)) == [
        {
            "목록키": "A-001",
            "제안이유": "본문에, 쉼표가, 많음",
            "시작일": "2024-01-02",
            "건수": "12",
        }
    ]


def test_unquoted_commas_do_not_merge_structured_name_columns(tmp_path) -> None:
    path = tmp_path / "ordinance.csv"
    path.write_text(
        "\n".join(
            [
                "연번,연도,지방자치단체,조례명,대표자,제개정,청구일,제안이유,공표청구개요,시작일,종료일,청구권자수,서명수,결과코드,처리상태,URL",
                (
                    "14,2019,충청남도 당진시,당진시 농민수당 지원 조례,김희봉 외 8명,제정,2019-08-13,"
                    "1. 제안이유 가. 시장은 농업의 공익적 가치와 농민의 권리를 보장·증진하기 위한 시책을 추진하여야 하며,"
                    " 이를 위한 농민수당 정책의 시행을 위해 행정적·재정적 지원 방안을 마련하여야 한다,"
                    "1. 공표청구사유 - 청구일 : 2019. 8. 13.(화),"
                    "2019-08-14,2019-11-13,166630,4546,1,청구완료(수정의결),"
                    "https://www.juminegov.go.kr/ordn/reqDtls?pSfLgsReqOnlineSno=201956800001001"
                ),
            ]
        ),
        encoding="utf-8",
    )

    assert list(iter_uploaded_rows(path)) == [
        {
            "연번": "14",
            "연도": "2019",
            "지방자치단체": "충청남도 당진시",
            "조례명": "당진시 농민수당 지원 조례",
            "대표자": "김희봉 외 8명",
            "제개정": "제정",
            "청구일": "2019-08-13",
            "제안이유": (
                "1. 제안이유 가. 시장은 농업의 공익적 가치와 농민의 권리를 보장·증진하기 위한 시책을 추진하여야 하며, "
                "이를 위한 농민수당 정책의 시행을 위해 행정적·재정적 지원 방안을 마련하여야 한다"
            ),
            "공표청구개요": "1. 공표청구사유 - 청구일 : 2019. 8. 13.(화)",
            "시작일": "2019-08-14",
            "종료일": "2019-11-13",
            "청구권자수": "166630",
            "서명수": "4546",
            "결과코드": "1",
            "처리상태": "청구완료(수정의결)",
            "URL": "https://www.juminegov.go.kr/ordn/reqDtls?pSfLgsReqOnlineSno=201956800001001",
        }
    ]
