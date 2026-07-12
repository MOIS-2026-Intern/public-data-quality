from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.adapters.presenters.pipeline_response import _response_from_pipeline_parts
from backend.application.dto import PipelineExecutionRequest, pipeline_data, pipeline_result
from backend.application.use_cases import PipelineExecutionResult
from backend.config.pipeline import (
    PIPELINE_PROGRESS_STEPS,
    REPORT_PROGRESS_STEP,
)
from .dependencies import WebAdapterDependencies, default_web_dependencies


@dataclass(frozen=True)
class PipelineRunResult:
    response: dict[str, Any]
    validation_rows: list[dict[str, str]]


def _resolve_dependencies(dependencies: WebAdapterDependencies | None) -> WebAdapterDependencies:
    return dependencies or default_web_dependencies()


def _pipeline_run_result(result: PipelineExecutionResult) -> PipelineRunResult:
    data = pipeline_data(result.result_state)
    return PipelineRunResult(
        response=_response_from_pipeline_parts(data, pipeline_result(result.result_state)),
        validation_rows=result.validation_rows,
    )


def run_pipeline(
    *,
    request: PipelineExecutionRequest,
    dependencies: WebAdapterDependencies | None = None,
) -> PipelineRunResult:
    result = _resolve_dependencies(dependencies).pipeline_analysis_use_case().run(request)
    return _pipeline_run_result(result)


def stream_pipeline(
    *,
    request: PipelineExecutionRequest,
    dependencies: WebAdapterDependencies | None = None,
):
    for pipeline_event in _resolve_dependencies(dependencies).pipeline_analysis_use_case().stream(request):
        if pipeline_event.get("kind") != "result":
            yield pipeline_event
            continue

        result = pipeline_event.get("result")
        yield {
            "kind": "result",
            "result": _pipeline_run_result(result),
        }


__all__ = [
    "PIPELINE_PROGRESS_STEPS",
    "REPORT_PROGRESS_STEP",
    "run_pipeline",
    "stream_pipeline",
]
