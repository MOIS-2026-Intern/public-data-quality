from __future__ import annotations

from typing import Any

from backend.application.dto import (
    PipelineExecutionRequest,
    PipelineState,
    pipeline_state_update,
)
from backend.application.ports import PipelineExecutorPort
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
    request: PipelineExecutionRequest,
) -> None:
    if not request.uploaded_dataset_csv and not request.dataset_id and not request.dataset_name:
        raise ValueError(PIPELINE_REQUEST_SOURCE_REQUIRED_ERROR)
    if not request.uploaded_dataset_csv and not request.meta_csv:
        raise ValueError(PIPELINE_REQUEST_META_CSV_REQUIRED_ERROR)


def _pipeline_input(request: PipelineExecutionRequest) -> PipelineState:
    return pipeline_state_update(request=request.to_pipeline_request())


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
    executor: PipelineExecutorPort,
    request: PipelineExecutionRequest,
):
    _validate_pipeline_request(request)
    graph_input = _pipeline_input(request)
    result_state: dict[str, Any] = dict(graph_input)
    step_positions = {node_name: index for index, (node_name, _) in enumerate(PIPELINE_PROGRESS_STEPS, start=1)}
    step_total = len(PIPELINE_PROGRESS_STEPS) + 1

    for update in executor.stream_updates(graph_input):
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
    executor: PipelineExecutorPort,
    request: PipelineExecutionRequest,
) -> dict[str, Any]:
    _validate_pipeline_request(request)
    return executor.run(_pipeline_input(request))
