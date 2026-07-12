from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from backend.application.dto import PipelineExecutionRequest

from .graph import build_graph


class LangGraphPipelineExecutor:
    def __init__(self, request: PipelineExecutionRequest):
        self._graph = build_graph(request)

    def run(self, pipeline_input: dict[str, Any]) -> dict[str, Any]:
        return self._graph.invoke(pipeline_input)

    def stream_updates(self, pipeline_input: dict[str, Any]) -> Iterable[dict[str, Any]]:
        return self._graph.stream(pipeline_input, stream_mode="updates")
