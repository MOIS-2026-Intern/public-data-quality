from __future__ import annotations

from backend.application.dto import PipelineExecutionRequest

from .executor import LangGraphPipelineExecutor


class LangGraphPipelineExecutorFactory:
    def build(self, request: PipelineExecutionRequest):
        return LangGraphPipelineExecutor(request)
