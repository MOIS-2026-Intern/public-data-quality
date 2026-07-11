from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import backend.adapters.web.analysis_execution as execution
from backend.infrastructure.io.sources import PreparedDataset


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
        payload, status_code = execution.analyze_prepared_datasets(prepared_datasets=[dataset], options={})
    finally:
        execution._analyze_dataset_item = original

    assert status_code == 200
    assert payload["batch"] is False
    assert payload["result"]["summary"]["dataset_name"] == "sample"
    assert payload["results"][0]["filename"] == "sample.csv"


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
        payload, status_code = execution.analyze_prepared_datasets(prepared_datasets=[dataset], options={})
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

    def fake_stream_pipeline(**kwargs):
        assert kwargs["uploaded_dataset_csv"] == str(dataset_path)
        assert kwargs["uploaded_dataset_name"] == "sample.csv"
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
            options={},
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
