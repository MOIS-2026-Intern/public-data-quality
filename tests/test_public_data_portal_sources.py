from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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
