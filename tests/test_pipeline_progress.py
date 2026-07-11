from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.application.use_cases.pipeline_runner import stream_pipeline_state


class _FakeGraph:
    def stream(self, graph_input, *, stream_mode):
        assert graph_input["uploaded_dataset_path"] == "uploaded.csv"
        assert stream_mode == "updates"
        for node_name in (
            "load_reference_data",
            "normalize_columns",
            "profile_values",
            "route_rules",
            "semantic_profile",
            "validate",
            "categorical_semantic_validate",
            "propose_repairs",
            "final_finding_verify",
            "verify_results",
        ):
            yield {node_name: {}}

    def invoke(self, graph_input):
        return graph_input


def test_stream_pipeline_state_emits_progress_for_final_finding_verification() -> None:
    events = list(
        stream_pipeline_state(
            _FakeGraph(),
            uploaded_dataset_csv="uploaded.csv",
        )
    )

    progress_nodes = [event["node"] for event in events if event["kind"] == "progress"]

    assert progress_nodes == [
        "load_reference_data",
        "normalize_columns",
        "profile_values",
        "route_rules",
        "semantic_profile",
        "validate",
        "categorical_semantic_validate",
        "propose_repairs",
        "final_finding_verify",
        "verify_results",
        "write_reports",
    ]
