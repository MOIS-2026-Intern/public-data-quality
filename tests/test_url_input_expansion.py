from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import backend.web as web
from backend.core.io.sources import PreparedDataset


def test_prepare_url_input_datasets_expands_downloaded_public_data_url_list(monkeypatch, tmp_path) -> None:
    list_url = "https://example.com/url-list.csv"
    first_download_url = (
        "https://www.data.go.kr/cmm/cmm/fileDownload.do"
        "?atchFileId=FILE_000000002449437&fileDetailSn=1&insertDataPrcus=N"
    )
    second_download_url = (
        "https://www.data.go.kr/cmm/cmm/fileDownload.do"
        "?atchFileId=FILE_000000001493356&fileDetailSn=1&insertDataPrcus=N"
    )
    list_path = tmp_path / "download_links.csv"
    list_path.write_text(f"{first_download_url}\n{second_download_url}\n", encoding="utf-8")
    first_path = tmp_path / "first.csv"
    second_path = tmp_path / "second.csv"
    first_path.write_text("name\nfirst\n", encoding="utf-8")
    second_path.write_text("name\nsecond\n", encoding="utf-8")

    def fake_prepare_url_datasets(url, output_dir):
        if url == list_url:
            return [PreparedDataset("download_links.csv", list_path, "url", "csv")]
        if url == first_download_url:
            return [PreparedDataset("first.csv", first_path, "url", "csv")]
        if url == second_download_url:
            return [PreparedDataset("second.csv", second_path, "url", "csv")]
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(web, "prepare_url_datasets", fake_prepare_url_datasets)

    prepared = web._prepare_url_input_datasets(list_url, str(tmp_path))

    assert [item.display_name for item in prepared] == ["first.csv", "second.csv"]
    assert [item.path.read_text(encoding="utf-8") for item in prepared] == ["name\nfirst\n", "name\nsecond\n"]


def test_prepare_url_input_datasets_keeps_general_url_dataset(monkeypatch, tmp_path) -> None:
    list_url = "https://example.com/service-urls.csv"
    service_url_path = tmp_path / "service_urls.csv"
    service_url_path.write_text("https://www.bokjiro.go.kr/service\nhttps://example.com/info\n", encoding="utf-8")

    def fake_prepare_url_datasets(url, output_dir):
        assert url == list_url
        return [PreparedDataset("service_urls.csv", service_url_path, "url", "csv")]

    monkeypatch.setattr(web, "prepare_url_datasets", fake_prepare_url_datasets)

    prepared = web._prepare_url_input_datasets(list_url, str(tmp_path))

    assert [item.display_name for item in prepared] == ["service_urls.csv"]
