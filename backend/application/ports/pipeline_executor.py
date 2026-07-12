from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Protocol


class PipelineExecutorPort(Protocol):
    def run(self, pipeline_input: dict[str, Any]) -> dict[str, Any]: ...

    def stream_updates(self, pipeline_input: dict[str, Any]) -> Iterable[dict[str, Any]]: ...
