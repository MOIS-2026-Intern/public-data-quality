from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.application.dto import PipelineExecutionRequest, pipeline_data
from backend.application.ports import PipelineExecutorFactoryPort
from .pipeline_runner import run_pipeline_state, stream_pipeline_state


@dataclass(frozen=True)
class PipelineExecutionResult:
    result_state: dict[str, Any]
    validation_rows: list[dict[str, str]]


class PipelineAnalysisUseCase:
    def __init__(self, executor_factory: PipelineExecutorFactoryPort):
        self.executor_factory = executor_factory

    def _build_result(self, result_state: dict[str, Any]) -> PipelineExecutionResult:
        return PipelineExecutionResult(
            result_state=result_state,
            validation_rows=pipeline_data(result_state).validation_rows,
        )

    def run(self, request: PipelineExecutionRequest) -> PipelineExecutionResult:
        executor = self.executor_factory.build(request)
        result_state = run_pipeline_state(executor, request)
        return self._build_result(result_state)

    def stream(self, request: PipelineExecutionRequest):
        executor = self.executor_factory.build(request)
        for pipeline_event in stream_pipeline_state(executor, request):
            if pipeline_event.get("kind") != "result":
                yield pipeline_event
                continue

            result_state = pipeline_event.get("result") or {}
            yield {
                "kind": "result",
                "result": self._build_result(result_state),
            }
