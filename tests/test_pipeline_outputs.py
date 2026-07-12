from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.infrastructure.reporting.pipeline_outputs import attach_report_paths


def test_attach_report_paths_uses_unique_relative_artifact_names(tmp_path) -> None:
    response = {
        "summary": {"dataset_name": "sample.csv", "column_count": 1, "row_count": 1},
        "preview_headers": ["value"],
        "preview_rows": [{"value": "1"}],
        "columns": [{"raw_name": "value"}],
        "findings": [],
    }
    validation_rows = [{"value": "1"}]

    first = attach_report_paths(response=response, validation_rows=validation_rows, output_dir=tmp_path)
    second = attach_report_paths(response=response, validation_rows=validation_rows, output_dir=tmp_path)

    first_csv = first["summary"]["validation_result_csv"]
    second_csv = second["summary"]["validation_result_csv"]
    first_report = first["summary"]["error_report_xlsx"]
    second_report = second["summary"]["error_report_xlsx"]

    assert Path(first_csv).name == first_csv
    assert Path(first_report).name == first_report
    assert first_csv != second_csv
    assert first_report != second_report
    assert (tmp_path / "results" / first_csv).exists()
    assert (tmp_path / "reports" / first_report).exists()
