from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

import backend.core.io.sources as sources


def test_prepare_url_datasets_resolves_data_go_kr_file_page(monkeypatch, tmp_path) -> None:
    page_url = "https://www.data.go.kr/data/15083323/fileData.do"
    api_url = "https://www.data.go.kr/tcs/dss/selectFileDataDownload.do"
    download_url = (
        "https://www.data.go.kr/cmm/cmm/fileDownload.do"
        "?atchFileId=FILE_123&fileDetailSn=7&insertDataPrcus=N"
    )
    html = """
        <input type="hidden" id="publicDataPk" value="15083323"/>
        <input type="hidden" id="publicDataDetailPk" value="uddi:abc"/>
        <a onclick="fileDetailObj.fn_fileDataDown('15083323', 'uddi:abc', '', '7', '1')">다운로드</a>
    """.encode("utf-8")
    calls: list[tuple[str, str]] = []

    def fake_fetch(url, *, method, headers=None, body=None):
        calls.append((url, method))
        if url == page_url:
            return html, "text/html; charset=UTF-8", ""
        if url == api_url:
            assert method == "POST"
            assert headers["X-Requested-With"] == "XMLHttpRequest"
            assert b"publicDataPk=15083323" in body
            assert b"publicDataDetailPk=uddi%3Aabc" in body
            return (
                json.dumps({"atchFileId": "FILE_123", "fileDetailSn": "7"}).encode("utf-8"),
                "application/json",
                "",
            )
        if url == download_url:
            assert headers["Referer"] == page_url
            return b"a,b\n1,2\n", "text/csv", 'attachment; filename="sample.csv"'
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(sources, "_fetch_remote", fake_fetch)

    prepared = sources.prepare_url_datasets(page_url, tmp_path)

    assert [(item.display_name, item.response_type) for item in prepared] == [("sample.csv", "csv")]
    assert prepared[0].path.read_text(encoding="utf-8") == "a,b\n1,2\n"
    assert calls == [(page_url, "GET"), (api_url, "POST"), (download_url, "GET")]


def test_prepare_url_datasets_uses_data_go_kr_content_url_fallback(monkeypatch, tmp_path) -> None:
    page_url = "https://www.data.go.kr/data/15083323/fileData.do"
    download_url = (
        "https://www.data.go.kr/cmm/cmm/fileDownload.do"
        "?atchFileId=FILE_DIRECT&fileDetailSn=1&insertDataPrcus=N"
    )
    html = """
        <script type="application/ld+json">
        {
            "distribution": [
                {
                    "@type": "DataDownload",
                    "contentUrl": "https:\\/\\/www.data.go.kr\\/cmm\\/cmm\\/fileDownload.do?atchFileId=FILE_DIRECT&amp;fileDetailSn=1&amp;insertDataPrcus=N"
                }
            ]
        }
        </script>
    """.encode("utf-8")

    def fake_fetch(url, *, method, headers=None, body=None):
        if url == page_url:
            return html, "text/html; charset=UTF-8", ""
        if url == download_url:
            return b"a,b\n1,2\n", "text/csv", 'attachment; filename="direct.csv"'
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(sources, "_fetch_remote", fake_fetch)

    prepared = sources.prepare_url_datasets(page_url, tmp_path)

    assert prepared[0].display_name == "direct.csv"
    assert prepared[0].response_type == "csv"


def test_prepare_url_datasets_accepts_data_go_kr_direct_download_url(monkeypatch, tmp_path) -> None:
    direct_url = (
        "https://www.data.go.kr/cmm/cmm/fileDownload.do"
        "?atchFileId=FILE_000000003111165&fileDetailSn=1&insertDataPrcus=N"
    )

    def fake_fetch(url, *, method, headers=None, body=None):
        assert url == direct_url
        assert method == "GET"
        assert headers["Referer"] == "https://www.data.go.kr/"
        assert body is None
        return b"a,b\n1,2\n", "application/octet-stream", ""

    monkeypatch.setattr(sources, "_fetch_remote", fake_fetch)

    prepared = sources.prepare_url_datasets(direct_url, tmp_path)

    assert prepared[0].display_name == "FILE_000000003111165_1.csv"
    assert prepared[0].response_type == "csv"
    assert prepared[0].path.read_text(encoding="utf-8") == "a,b\n1,2\n"


def test_prepare_url_datasets_uses_data_go_kr_direct_download_filename(monkeypatch, tmp_path) -> None:
    direct_url = "https://www.data.go.kr/cmm/cmm/fileDownload.do?atchFileId=FILE_123&fileDetailSn=7"

    def fake_fetch(url, *, method, headers=None, body=None):
        return (
            b"a,b\n1,2\n",
            "application/octet-stream",
            "attachment; filename*=UTF-8''%ED%85%8C%EC%8A%A4%ED%8A%B8.csv",
        )

    monkeypatch.setattr(sources, "_fetch_remote", fake_fetch)

    prepared = sources.prepare_url_datasets(direct_url, tmp_path)

    assert prepared[0].display_name == "테스트.csv"
    assert prepared[0].response_type == "csv"


def test_prepare_url_datasets_rejects_data_go_kr_direct_download_html(monkeypatch, tmp_path) -> None:
    direct_url = "https://www.data.go.kr/cmm/cmm/fileDownload.do?atchFileId=FILE_123&fileDetailSn=7"

    def fake_fetch(url, *, method, headers=None, body=None):
        return b"<!doctype html><html><body>error</body></html>", "text/html", ""

    monkeypatch.setattr(sources, "_fetch_remote", fake_fetch)

    with pytest.raises(ValueError, match="파일 대신 HTML"):
        sources.prepare_url_datasets(direct_url, tmp_path)
