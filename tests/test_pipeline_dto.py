from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.application.dto import (
    AgentTrace,
    PipelineExecutionRequest,
    merge_state_updates,
    pipeline_data,
    pipeline_request,
    pipeline_result,
    pipeline_rows,
    update_pipeline_data,
    update_pipeline_result,
)
from backend.domain.entities.models import ValidationFinding
from backend.domain.services.normalization import build_column_profile


def test_pipeline_request_preserves_missing_values_as_none() -> None:
    request = pipeline_request({})

    assert request.meta_csv_path is None
    assert request.uploaded_dataset_path is None
    assert request.uploaded_dataset_name is None
    assert request.dataset_id is None
    assert request.dataset_name is None


def test_pipeline_execution_request_builds_pipeline_request() -> None:
    request = PipelineExecutionRequest(
        dataset_id="d1",
        dataset_name="dataset",
        meta_csv="meta.csv",
        uploaded_dataset_csv="uploaded.csv",
        uploaded_dataset_name="uploaded",
        use_llm_agents=True,
        llm_model="gpt-4o",
        llm_fast_model="gpt-4o-mini",
        llm_strong_model="gpt-4o",
    ).to_pipeline_request()

    assert request.dataset_id == "d1"
    assert request.dataset_name == "dataset"
    assert request.meta_csv_path == "meta.csv"
    assert request.uploaded_dataset_path == "uploaded.csv"
    assert request.uploaded_dataset_name == "uploaded"
    assert request.use_llm_agents is True


def test_pipeline_rows_preserve_falsy_values() -> None:
    rows = pipeline_rows(
        {
            "validation_rows": [
                {"count": 0, "ratio": 0.0, "enabled": False, "missing": None},
            ]
        }
    )

    assert rows == [{"count": "0", "ratio": "0.0", "enabled": "False", "missing": ""}]


def test_pipeline_accessors_reuse_existing_typed_collections() -> None:
    validation_rows = [{"value": "0"}]
    columns = [build_column_profile("COL1", "response")]
    findings = [
        ValidationFinding(
            column_name="COL1",
            severity="error",
            finding_type="issue",
            display_label="오류",
            category_group="형식",
            category_label="형식",
            criterion_name="형식 검증",
            rule_id="invalid_format",
            message="형식이 올바르지 않습니다.",
        )
    ]
    traces = [AgentTrace(agent_name="validator", action="run")]
    state = {
        "validation_rows": validation_rows,
        "columns": columns,
        "findings": findings,
        "agent_traces": traces,
    }

    assert pipeline_rows(state) is validation_rows
    assert pipeline_data(state).validation_rows is validation_rows
    assert pipeline_data(state).columns is columns
    assert pipeline_result(state).findings is findings
    assert pipeline_result(state).agent_traces is traces


def test_update_pipeline_data_returns_partial_update_only() -> None:
    validation_rows = [{"value": "0"}]
    state = {
        "validation_rows": validation_rows,
        "columns": [build_column_profile("COL1", "response")],
    }

    updated = update_pipeline_data(state, preview_headers=["COL1"])

    assert updated == {"preview_headers": ["COL1"]}


def test_merge_state_updates_preserves_prior_partial_changes() -> None:
    validation_rows = [{"value": "0"}]
    state = {
        "validation_rows": validation_rows,
        "preview_headers": ["OLD"],
        "summary": {"old": 1},
    }

    merged = {
        **state,
        **merge_state_updates(
            update_pipeline_data(state, preview_headers=["COL1"]),
            update_pipeline_result(state, summary={"new": 2}),
        ),
    }

    assert merged["validation_rows"] is validation_rows
    assert merged["preview_headers"] == ["COL1"]
    assert merged["summary"] == {"new": 2}


@pytest.mark.parametrize(
    ("state", "message"),
    [
        ({"use_llm_agents": "false"}, "use_llm_agents must be a bool."),
        ({"dataset_id": 1}, "dataset_id must be a string."),
        ({"llm_model": ["gpt-4o"]}, "llm_model must be a string."),
    ],
)
def test_pipeline_request_fails_fast_on_invalid_request_values(state, message: str) -> None:
    with pytest.raises(TypeError, match=message):
        pipeline_request(state)


@pytest.mark.parametrize(
    ("state", "message"),
    [
        ({"columns": [{"raw_name": "COL1"}]}, "columns must contain only ColumnProfile instances."),
        (
            {"findings": [{"column_name": "COL1"}]},
            "findings must contain only ValidationFinding instances.",
        ),
        (
            {"agent_traces": [{"agent_name": "validator"}]},
            "agent_traces must contain only AgentTrace instances.",
        ),
    ],
)
def test_pipeline_accessors_fail_fast_on_invalid_typed_payloads(state, message: str) -> None:
    with pytest.raises(TypeError, match=message):
        if "columns" in state:
            pipeline_data(state)
        else:
            pipeline_result(state)
