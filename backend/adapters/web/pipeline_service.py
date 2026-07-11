from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
from backend.config.reporting import (
    VALIDATION_OUTPUT_BASE_DIR_NAME,
    VALIDATION_OUTPUT_DIR_ENV_VAR,
    VALIDATION_OUTPUT_DIR_NAME,
)
from backend.infrastructure.orchestration.graph import build_graph


@dataclass(frozen=True)
class PipelineRunResult:
    response: dict[str, Any]
    validation_rows: list[dict[str, str]]


def validation_output_dir(base_dir: Path | None = None) -> Path:
    if base_dir is not None:
        base = Path(base_dir)
    else:
        configured_dir = os.getenv(VALIDATION_OUTPUT_DIR_ENV_VAR)
        if configured_dir:
            return Path(configured_dir)
        if os.getenv("VERCEL"):
            base = Path("/tmp") / VALIDATION_OUTPUT_BASE_DIR_NAME
        else:
            base = Path(tempfile.gettempdir()) / VALIDATION_OUTPUT_BASE_DIR_NAME
    return base / VALIDATION_OUTPUT_DIR_NAME


def _pipeline_run_result(result_state: dict[str, Any]) -> PipelineRunResult:
    data = pipeline_data(result_state)
    return PipelineRunResult(
        response=_response_from_pipeline_parts(data, pipeline_result(result_state)),
        validation_rows=data.validation_rows,
    )


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
) -> PipelineRunResult:
    graph = build_graph(
        use_llm_agents=use_llm_agents,
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
    return _pipeline_run_result(result_state)


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
        use_llm_agents=use_llm_agents,
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
        yield {
            "kind": "result",
            "result": _pipeline_run_result(result_state),
        }


__all__ = [
    "PIPELINE_PROGRESS_STEPS",
    "REPORT_PROGRESS_STEP",
    "run_pipeline",
    "stream_pipeline",
    "validation_output_dir",
]
