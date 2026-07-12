from __future__ import annotations

from typing import Protocol

from backend.application.dto import PipelineExecutionRequest

from .pipeline_executor import PipelineExecutorPort


class PipelineExecutorFactoryPort(Protocol):
    def build(self, request: PipelineExecutionRequest) -> PipelineExecutorPort: ...
