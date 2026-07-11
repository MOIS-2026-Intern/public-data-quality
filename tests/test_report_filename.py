from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.infrastructure.reporting.workbooks import _report_filename
from backend.adapters.web.analysis_support import _download_name


def test_error_report_filename_preserves_korean_dataset_full_name() -> None:
    filename = _report_filename("화성시_어린이보호구역.csv")

    assert filename == "화성시_어린이보호구역.xlsx"


def test_error_report_filename_keeps_existing_xlsx_extension() -> None:
    filename = _report_filename("수정_행정안전부_자원봉사.xlsx")

    assert filename == "수정_행정안전부_자원봉사.xlsx"


def test_error_report_filename_replaces_only_filesystem_unsafe_characters() -> None:
    filename = _report_filename("공공데이터/복지:서비스?.csv")

    assert filename == "공공데이터_복지_서비스.xlsx"


def test_download_name_preserves_korean() -> None:
    assert _download_name("화성시_어린이보호구역.xlsx") == "화성시_어린이보호구역.xlsx"
