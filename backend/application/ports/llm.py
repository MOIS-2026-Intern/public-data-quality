from __future__ import annotations

from typing import Protocol


class LLMResponsePort(Protocol):
    content: str


class JsonLLMPort(Protocol):
    model_name: str
    last_error: str
    last_response_preview: str

    @property
    def enabled(self) -> bool: ...

    def invoke_json(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
    ) -> LLMResponsePort | None: ...
