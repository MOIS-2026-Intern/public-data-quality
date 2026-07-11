from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Protocol


class PipelineGraphPort(Protocol):
    def invoke(self, graph_input: dict[str, Any]) -> dict[str, Any]: ...

    def stream(
        self,
        graph_input: dict[str, Any],
        *,
        stream_mode: str,
    ) -> Iterable[Any]: ...
