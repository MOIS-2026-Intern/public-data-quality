from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from openpyxl import Workbook

from backend.infrastructure.io.url_lists import load_url_list


def test_load_url_list_from_txt(tmp_path) -> None:
    path = tmp_path / "urls.txt"
    path.write_text(
        "\n".join(
            [
                "https://data.seoul.go.kr/api/file.csv",
                "설명: https://www.data.go.kr/dataset/15012345/fileData.do,",
                "https://data.seoul.go.kr/api/file.csv",
            ]
        ),
        encoding="utf-8",
    )

    assert load_url_list(path) == [
        "https://data.seoul.go.kr/api/file.csv",
        "https://www.data.go.kr/dataset/15012345/fileData.do",
    ]


def test_load_url_list_from_csv(tmp_path) -> None:
    path = tmp_path / "urls.csv"
    path.write_text(
        "\n".join(
            [
                "url",
                "https://www.data.go.kr/cmm/cmm/fileDownload.do?atchFileId=FILE_1&fileDetailSn=1&insertDataPrcus=N",
                "https://www.data.go.kr/cmm/cmm/fileDownload.do?atchFileId=FILE_2&fileDetailSn=1&insertDataPrcus=N",
            ]
        ),
        encoding="utf-8",
    )

    assert load_url_list(path) == [
        "https://www.data.go.kr/cmm/cmm/fileDownload.do?atchFileId=FILE_1&fileDetailSn=1&insertDataPrcus=N",
        "https://www.data.go.kr/cmm/cmm/fileDownload.do?atchFileId=FILE_2&fileDetailSn=1&insertDataPrcus=N",
    ]
    assert load_url_list(path, strict=True) == [
        "https://www.data.go.kr/cmm/cmm/fileDownload.do?atchFileId=FILE_1&fileDetailSn=1&insertDataPrcus=N",
        "https://www.data.go.kr/cmm/cmm/fileDownload.do?atchFileId=FILE_2&fileDetailSn=1&insertDataPrcus=N",
    ]


def test_strict_url_list_rejects_descriptive_table(tmp_path) -> None:
    path = tmp_path / "urls.csv"
    path.write_text("name,url\n서울,https://example.com/seoul.csv\n", encoding="utf-8")

    try:
        load_url_list(path, strict=True)
    except ValueError as exc:
        assert "URL을 찾지 못했습니다" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("ValueError was not raised")


def test_load_url_list_from_xlsx(tmp_path) -> None:
    path = tmp_path / "urls.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "URLs"
    sheet.append(["name", "url"])
    sheet.append(["서울", "https://example.com/seoul.csv"])
    sheet.append(["부산", "https://example.com/busan.csv"])
    workbook.save(path)
    workbook.close()

    assert load_url_list(path) == [
        "https://example.com/seoul.csv",
        "https://example.com/busan.csv",
    ]


def test_load_url_list_rejects_file_without_urls(tmp_path) -> None:
    path = tmp_path / "urls.txt"
    path.write_text("url 목록\n데이터 없음", encoding="utf-8")

    try:
        load_url_list(path)
    except ValueError as exc:
        assert "URL을 찾지 못했습니다" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("ValueError was not raised")
