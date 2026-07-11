from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.application.services.pipeline.profiling import profile_values
from backend.domain.entities.models import DatasetMeta
from backend.domain.services.normalization import build_column_profile


class _StreamingDatasetGateway:
    def __init__(self, rows):
        self._rows = rows
        self.calls = 0

    def iter_uploaded_rows(self, file_path):
        assert file_path == "uploaded.csv"
        self.calls += 1
        yield from self._rows


def test_profile_values_preserves_buffered_and_streamed_rows() -> None:
    rows = [{"COL1": f"value-{index}"} for index in range(55)]
    gateway = _StreamingDatasetGateway(rows)
    state = {
        "uploaded_dataset_path": "uploaded.csv",
        "columns": [build_column_profile("COL1", "response")],
        "dataset_meta": DatasetMeta(
            dataset_id="upload:test",
            dataset_name="테스트 데이터",
            response_fields=["COL1"],
        ),
        "agent_traces": [],
    }

    result = profile_values(state, dataset_gateway=gateway)

    assert gateway.calls == 1
    assert result["dataset_meta"].total_rows == 55
    assert len(result["validation_rows"]) == 55
    assert result["validation_rows"][0] == {"COL1": "value-0"}
    assert result["validation_rows"][-1] == {"COL1": "value-54"}


def test_profile_values_preserves_falsy_values_in_buffered_and_streamed_rows() -> None:
    rows = [{"COL1": 0}, {"COL1": False}]
    rows.extend({"COL1": f"value-{index}"} for index in range(2, 51))
    rows.extend([{"COL1": 0.0}, {"COL1": None}, {"COL1": "last"}])
    gateway = _StreamingDatasetGateway(rows)
    state = {
        "uploaded_dataset_path": "uploaded.csv",
        "columns": [build_column_profile("COL1", "response")],
        "dataset_meta": DatasetMeta(
            dataset_id="upload:test",
            dataset_name="테스트 데이터",
            response_fields=["COL1"],
        ),
        "agent_traces": [],
    }

    result = profile_values(state, dataset_gateway=gateway)

    assert result["validation_rows"][0] == {"COL1": "0"}
    assert result["validation_rows"][1] == {"COL1": "False"}
    assert result["validation_rows"][51] == {"COL1": "0.0"}
    assert result["validation_rows"][52] == {"COL1": ""}
