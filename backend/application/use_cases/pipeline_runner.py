from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.application.dto import PipelineRequest, PipelineState, pipeline_state_update
from backend.application.ports import PipelineGraphPort
from backend.config.pipeline import (
    PIPELINE_PROGRESS_ACTIVE_MESSAGE_SUFFIX,
    PIPELINE_PROGRESS_DONE_MESSAGE_SUFFIX,
    PIPELINE_PROGRESS_STEPS,
    PIPELINE_PROGRESS_STEP_LABELS,
    PIPELINE_REQUEST_META_CSV_REQUIRED_ERROR,
    PIPELINE_REQUEST_SOURCE_REQUIRED_ERROR,
    REPORT_PROGRESS_STEP,
)


def _validate_pipeline_request(
    *,
    dataset_id: str | None,
    dataset_name: str | None,
    meta_csv: str | None,
    uploaded_dataset_csv: str | None,
) -> None:
    if not uploaded_dataset_csv and not dataset_id and not dataset_name:
        raise ValueError(PIPELINE_REQUEST_SOURCE_REQUIRED_ERROR)
    if not uploaded_dataset_csv and not meta_csv:
        raise ValueError(PIPELINE_REQUEST_META_CSV_REQUIRED_ERROR)


def _pipeline_input(
    *,
    dataset_id: str | None,
    dataset_name: str | None,
    meta_csv: str | None,
    uploaded_dataset_csv: str | None,
    uploaded_dataset_name: str | None,
    use_llm_agents: bool,
    llm_model: str | None,
    llm_fast_model: str | None,
    llm_strong_model: str | None,
) -> PipelineState:
    return pipeline_state_update(
        request=PipelineRequest(
            dataset_id=dataset_id,
            dataset_name=dataset_name,
            meta_csv_path=str(Path(meta_csv)) if meta_csv else None,
            uploaded_dataset_path=str(Path(uploaded_dataset_csv)) if uploaded_dataset_csv else None,
            uploaded_dataset_name=uploaded_dataset_name,
            use_llm_agents=use_llm_agents,
            llm_model=llm_model,
            llm_fast_model=llm_fast_model,
            llm_strong_model=llm_strong_model,
        )
    )


def _pipeline_progress_event(
    node_name: str,
    step_index: int,
    step_total: int,
    *,
    step_labels: dict[str, str],
    report_step_name: str,
) -> dict[str, Any]:
    label = step_labels.get(node_name, node_name)
    message = (
        f"{label}{PIPELINE_PROGRESS_ACTIVE_MESSAGE_SUFFIX}"
        if node_name == report_step_name
        else f"{label}{PIPELINE_PROGRESS_DONE_MESSAGE_SUFFIX}"
    )
    return {
        "node": node_name,
        "stage_label": label,
        "stage_index": step_index,
        "stage_total": step_total,
        "message": message,
    }


def stream_pipeline_state(
    graph: PipelineGraphPort,
    *,
    dataset_id: str | None = None,
    dataset_name: str | None = None,
    meta_csv: str | None = None,
    uploaded_dataset_csv: str | None = None,
    uploaded_dataset_name: str | None = None,
    use_llm_agents: bool = False,
    llm_model: str | None = None,
    llm_fast_model: str | None = None,
    llm_strong_model: str | None = None,
):
    _validate_pipeline_request(
        dataset_id=dataset_id,
        dataset_name=dataset_name,
        meta_csv=meta_csv,
        uploaded_dataset_csv=uploaded_dataset_csv,
    )

    graph_input = _pipeline_input(
        dataset_id=dataset_id,
        dataset_name=dataset_name,
        meta_csv=meta_csv,
        uploaded_dataset_csv=uploaded_dataset_csv,
        uploaded_dataset_name=uploaded_dataset_name,
        use_llm_agents=use_llm_agents,
        llm_model=llm_model,
        llm_fast_model=llm_fast_model,
        llm_strong_model=llm_strong_model,
    )
    result_state: dict[str, Any] = dict(graph_input)
    step_positions = {node_name: index for index, (node_name, _) in enumerate(PIPELINE_PROGRESS_STEPS, start=1)}
    step_total = len(PIPELINE_PROGRESS_STEPS) + 1

    for update in graph.stream(graph_input, stream_mode="updates"):
        if not isinstance(update, dict):
            continue
        for node_name, node_update in update.items():
            if isinstance(node_update, dict):
                result_state.update(node_update)
            step_index = step_positions.get(node_name)
            if step_index is None:
                continue
            yield {
                "kind": "progress",
                **_pipeline_progress_event(
                    node_name,
                    step_index,
                    step_total,
                    step_labels=PIPELINE_PROGRESS_STEP_LABELS,
                    report_step_name=REPORT_PROGRESS_STEP[0],
                ),
            }

    report_step_index = len(PIPELINE_PROGRESS_STEPS) + 1
    yield {
        "kind": "progress",
        **_pipeline_progress_event(
            REPORT_PROGRESS_STEP[0],
            report_step_index,
            step_total,
            step_labels=PIPELINE_PROGRESS_STEP_LABELS,
            report_step_name=REPORT_PROGRESS_STEP[0],
        ),
    }
    yield {
        "kind": "result",
        "result": result_state,
    }


def run_pipeline_state(
    graph: PipelineGraphPort,
    *,
    dataset_id: str | None = None,
    dataset_name: str | None = None,
    meta_csv: str | None = None,
    uploaded_dataset_csv: str | None = None,
    uploaded_dataset_name: str | None = None,
    use_llm_agents: bool = False,
    llm_model: str | None = None,
    llm_fast_model: str | None = None,
    llm_strong_model: str | None = None,
) -> dict[str, Any]:
    _validate_pipeline_request(
        dataset_id=dataset_id,
        dataset_name=dataset_name,
        meta_csv=meta_csv,
        uploaded_dataset_csv=uploaded_dataset_csv,
    )
    return graph.invoke(
        _pipeline_input(
            dataset_id=dataset_id,
            dataset_name=dataset_name,
            meta_csv=meta_csv,
            uploaded_dataset_csv=uploaded_dataset_csv,
            uploaded_dataset_name=uploaded_dataset_name,
            use_llm_agents=use_llm_agents,
            llm_model=llm_model,
            llm_fast_model=llm_fast_model,
            llm_strong_model=llm_strong_model,
        )
    )
