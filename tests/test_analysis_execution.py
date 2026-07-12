from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import backend.adapters.web.analysis_execution as execution
from backend.adapters.web.dependencies import WebAdapterDependencies
from backend.application.dto import PipelineExecutionRequest
from backend.infrastructure.io.sources import PreparedDataset


def _dependencies() -> WebAdapterDependencies:
    return WebAdapterDependencies(
        pipeline_analysis_use_case=lambda: None,
        validation_output_dir=lambda base_dir=None: Path("/tmp"),
        attach_report_paths=lambda **kwargs: kwargs["response"],
        write_batch_error_report=lambda **kwargs: Path("/tmp/batch_report.xlsx"),
        public_download_name=lambda filename, default_suffix=".xlsx": filename,
        prepare_saved_dataset=lambda *args, **kwargs: [],
        prepare_url_datasets=lambda *args, **kwargs: [],
        prepare_api_datasets=lambda *args, **kwargs: [],
        load_url_list=lambda *args, **kwargs: [],
    )


def test_analyze_prepared_datasets_wraps_single_success() -> None:
    dataset = PreparedDataset(
        display_name="sample.csv",
        path=Path("/tmp/sample.csv"),
        source_type="file",
        response_type="csv",
    )

    original = execution._analyze_dataset_item
    execution._analyze_dataset_item = lambda **_: {
        "ok": True,
        "filename": "sample.csv",
        "result": {"summary": {"dataset_name": "sample", "row_count": 1}, "findings": []},
    }
    try:
        payload, status_code = execution.analyze_prepared_datasets(
            prepared_datasets=[dataset],
            options=PipelineExecutionRequest(),
        )
    finally:
        execution._analyze_dataset_item = original

    assert status_code == 200
    assert payload["batch"] is False
    assert payload["result"]["summary"]["dataset_name"] == "sample"
    assert payload["results"][0]["filename"] == "sample.csv"


def test_analyze_prepared_datasets_generates_batch_report_path() -> None:
    datasets = [
        PreparedDataset(display_name="a.csv", path=Path("/tmp/a.csv"), source_type="file", response_type="csv"),
        PreparedDataset(display_name="b.csv", path=Path("/tmp/b.csv"), source_type="file", response_type="csv"),
    ]

    original = execution._analyze_dataset_item
    results = iter(
        [
            {
                "ok": True,
                "filename": "a.csv",
                "result": {"summary": {"dataset_name": "a", "row_count": 1}, "findings": []},
            },
            {
                "ok": True,
                "filename": "b.csv",
                "result": {"summary": {"dataset_name": "b", "row_count": 2}, "findings": []},
            },
        ]
    )
    execution._analyze_dataset_item = lambda **_: next(results)
    try:
        payload, status_code = execution.analyze_prepared_datasets(
            prepared_datasets=datasets,
            options=PipelineExecutionRequest(),
            dependencies=_dependencies(),
        )
    finally:
        execution._analyze_dataset_item = original

    assert status_code == 200
    assert payload["batch"] is True
    assert payload["summary"]["error_report_xlsx"] == "batch_report.xlsx"


def test_analyze_prepared_datasets_wraps_single_failure() -> None:
    dataset = PreparedDataset(
        display_name="sample.csv",
        path=Path("/tmp/sample.csv"),
        source_type="file",
        response_type="csv",
    )

    original = execution._analyze_dataset_item
    execution._analyze_dataset_item = lambda **_: {
        "ok": False,
        "filename": "sample.csv",
        "error": "boom",
    }
    try:
        payload, status_code = execution.analyze_prepared_datasets(
            prepared_datasets=[dataset],
            options=PipelineExecutionRequest(),
        )
    finally:
        execution._analyze_dataset_item = original

    assert status_code == 400
    assert payload["batch"] is False
    assert payload["result"] is None
    assert payload["error"] == "boom"


def test_stream_analysis_events_emits_final_payload_and_cleans_up(monkeypatch, tmp_path) -> None:
    dataset_path = tmp_path / "sample.csv"
    dataset_path.write_text("value\n1\n", encoding="utf-8")
    dataset = PreparedDataset(display_name="sample.csv", path=dataset_path, source_type="file", response_type="csv")
    cleanup_calls = {"count": 0}

    def fake_stream_pipeline(*, request, dependencies):
        assert dependencies is not None
        assert request.uploaded_dataset_csv == str(dataset_path)
        assert request.uploaded_dataset_name == "sample.csv"
        yield {
            "kind": "progress",
            "node": "load_reference_data",
            "stage_label": "입력 형식 확인",
            "stage_index": 1,
            "stage_total": 11,
            "message": "입력 형식 확인 완료",
        }
        yield {
            "kind": "result",
            "result": {"summary": {"dataset_name": "sample", "row_count": 1}, "findings": []},
        }

    monkeypatch.setattr(execution, "stream_pipeline", fake_stream_pipeline)

    chunks = list(
        execution.stream_analysis_events(
            prepared_datasets=[dataset],
            options=PipelineExecutionRequest(),
            cleanup=lambda: cleanup_calls.__setitem__("count", cleanup_calls["count"] + 1),
        )
    )
    events = [json.loads(chunk.decode("utf-8")) for chunk in chunks]

    assert cleanup_calls["count"] == 1
    assert events[0]["type"] == "progress"
    assert events[-1]["type"] == "final"
    assert events[-1]["payload"]["batch"] is False
    assert events[-1]["payload"]["result"]["summary"]["dataset_name"] == "sample"
    assert events[-1]["payload"]["summary"]["dataset_name"] == "sample"


def test_stream_analysis_events_emits_batch_report_path_for_batch(monkeypatch, tmp_path) -> None:
    first_path = tmp_path / "first.csv"
    second_path = tmp_path / "second.csv"
    first_path.write_text("value\n1\n", encoding="utf-8")
    second_path.write_text("value\n2\n", encoding="utf-8")
    datasets = [
        PreparedDataset(display_name="first.csv", path=first_path, source_type="file", response_type="csv"),
        PreparedDataset(display_name="second.csv", path=second_path, source_type="file", response_type="csv"),
    ]

    def fake_stream_pipeline(*, request, dependencies):
        yield {
            "kind": "result",
            "result": {"summary": {"dataset_name": request.uploaded_dataset_name, "row_count": 1}, "findings": []},
        }

    monkeypatch.setattr(execution, "stream_pipeline", fake_stream_pipeline)

    chunks = list(
        execution.stream_analysis_events(
            prepared_datasets=datasets,
            options=PipelineExecutionRequest(),
            dependencies=_dependencies(),
            cleanup=lambda: None,
        )
    )
    events = [json.loads(chunk.decode("utf-8")) for chunk in chunks]

    assert events[-1]["type"] == "final"
    assert events[-1]["payload"]["batch"] is True
    assert events[-1]["payload"]["summary"]["error_report_xlsx"] == "batch_report.xlsx"
