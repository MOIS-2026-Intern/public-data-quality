from __future__ import annotations

import os
from pathlib import Path

from backend.adapters.presenters.pipeline_response import _response_from_pipeline_parts
from backend.application.dto import pipeline_data, pipeline_result
from backend.application.use_cases.pipeline_runner import (
    run_pipeline_state,
    stream_pipeline_state,
)
from backend.config.pipeline import (
    PIPELINE_PROGRESS_STEPS,
    REPORT_PROGRESS_STEP,
)
from backend.config.reporting import VALIDATION_OUTPUT_DIR_NAME
from backend.infrastructure.orchestration.graph import build_graph
from backend.infrastructure.reporting.pipeline_outputs import attach_report_paths


def validation_output_dir(base_dir: Path | None = None) -> Path:
    if os.getenv("VERCEL") and base_dir is None:
        return Path("/tmp") / VALIDATION_OUTPUT_DIR_NAME
    base = base_dir or Path(__file__).resolve().parents[2]
    return base / VALIDATION_OUTPUT_DIR_NAME


def run_pipeline(
    *,
    dataset_id: str | None = None,
    dataset_name: str | None = None,
    meta_csv: str | None = None,
    uploaded_dataset_csv: str | None = None,
    uploaded_dataset_name: str | None = None,
    use_llm_agents: bool = False,
    openai_api_key: str | None = None,
    llm_model: str | None = None,
    llm_fast_model: str | None = None,
    llm_strong_model: str | None = None,
) -> dict:
    graph = build_graph(
        openai_api_key=openai_api_key,
        llm_model=llm_model,
        llm_fast_model=llm_fast_model,
        llm_strong_model=llm_strong_model,
    )
    result_state = run_pipeline_state(
        graph,
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
    data = pipeline_data(result_state)
    return attach_report_paths(
        response=_response_from_pipeline_parts(data, pipeline_result(result_state)),
        validation_rows=data.validation_rows,
        output_dir=validation_output_dir(),
    )


def stream_pipeline(
    *,
    dataset_id: str | None = None,
    dataset_name: str | None = None,
    meta_csv: str | None = None,
    uploaded_dataset_csv: str | None = None,
    uploaded_dataset_name: str | None = None,
    use_llm_agents: bool = False,
    openai_api_key: str | None = None,
    llm_model: str | None = None,
    llm_fast_model: str | None = None,
    llm_strong_model: str | None = None,
):
    graph = build_graph(
        openai_api_key=openai_api_key,
        llm_model=llm_model,
        llm_fast_model=llm_fast_model,
        llm_strong_model=llm_strong_model,
    )
    for pipeline_event in stream_pipeline_state(
        graph,
        dataset_id=dataset_id,
        dataset_name=dataset_name,
        meta_csv=meta_csv,
        uploaded_dataset_csv=uploaded_dataset_csv,
        uploaded_dataset_name=uploaded_dataset_name,
        use_llm_agents=use_llm_agents,
        llm_model=llm_model,
        llm_fast_model=llm_fast_model,
        llm_strong_model=llm_strong_model,
    ):
        if pipeline_event.get("kind") != "result":
            yield pipeline_event
            continue

        result_state = pipeline_event.get("result") or {}
        data = pipeline_data(result_state)
        yield {
            "kind": "result",
            "result": attach_report_paths(
                response=_response_from_pipeline_parts(data, pipeline_result(result_state)),
                validation_rows=data.validation_rows,
                output_dir=validation_output_dir(),
            ),
        }


__all__ = [
    "PIPELINE_PROGRESS_STEPS",
    "REPORT_PROGRESS_STEP",
    "run_pipeline",
    "stream_pipeline",
    "validation_output_dir",
]
