from __future__ import annotations

from typing import Any

from backend.application.shared import parse_json_content
from backend.application.dto import PipelineState, require_dataset_meta
from backend.application.ports import JsonLLMPort
from backend.application.prompts.resolution import (
    SEMANTIC_PROFILE_SYSTEM_PROMPT,
    semantic_profile_batch_prompt,
)
from backend.config.llm import (
    LLM_SEMANTIC_PROFILE_CONFIDENCE_DEFAULT,
    LLM_STRONG_FALLBACK_CONFIDENCE,
)
from backend.domain.entities.models import ColumnProfile
from .confidence import coerce_resolution_confidence


class LLMSemanticProfiler:
    def __init__(
        self,
        *,
        fast_llm: JsonLLMPort | None = None,
        strong_llm: JsonLLMPort | None = None,
    ):
        self._llm = fast_llm
        self._strong_llm = strong_llm
        self.fast_model_name = getattr(fast_llm, "model_name", "")
        self.strong_model_name = getattr(strong_llm, "model_name", self.fast_model_name)
        self.model_name = self.fast_model_name
        self.last_error = ""
        self.last_response_preview = ""
        self.last_model_name = self.fast_model_name
        self.last_stage = "fast"

    @property
    def enabled(self) -> bool:
        return self._llm is not None and self._llm.enabled

    def _client(self):
        return self._llm if self.enabled else None

    @property
    def _strong_enabled(self) -> bool:
        return (
            self._strong_llm is not None
            and
            bool(self.strong_model_name)
            and self.strong_model_name != self.fast_model_name
            and self._strong_llm.enabled
        )

    def _record_attempt(self, llm: JsonLLMPort, stage: str) -> None:
        self.last_error = llm.last_error
        self.last_response_preview = llm.last_response_preview
        self.last_model_name = llm.model_name
        self.last_stage = stage

    def _invoke_json_payload(
        self,
        prompt: str,
        *,
        system_prompt: str,
    ) -> dict[str, Any] | None:
        fast_payload = self._invoke_json_payload_once(
            self._llm,
            "fast",
            prompt,
            system_prompt=system_prompt,
        )
        if fast_payload is not None and not self._profile_needs_strong(fast_payload):
            return fast_payload

        if self._strong_enabled:
            strong_payload = self._invoke_json_payload_once(
                self._strong_llm,
                "strong",
                prompt,
                system_prompt=system_prompt,
            )
            if strong_payload is not None:
                strong_payload["_llm_escalated"] = True
                if fast_payload is not None:
                    strong_payload["_llm_fast_confidence"] = fast_payload.get("confidence")
                return strong_payload

        return fast_payload

    def _invoke_json_payload_once(
        self,
        llm: JsonLLMPort,
        stage: str,
        prompt: str,
        *,
        system_prompt: str,
    ) -> dict[str, Any] | None:
        response = llm.invoke_json(prompt, system_prompt=system_prompt)
        self._record_attempt(llm, stage)
        if response is None:
            return None

        payload = parse_json_content(response.content)
        if payload is None:
            llm.last_error = f"llm_parse_error:{response.content[:200]}"
            self._record_attempt(llm, stage)
            return None

        payload["_llm_model"] = llm.model_name
        payload["_llm_stage"] = stage
        payload["_llm_escalated"] = False
        self._record_attempt(llm, stage)
        return payload

    @staticmethod
    def _profile_needs_strong(payload: dict[str, Any]) -> bool:
        if payload.get("confidence") is None:
            return True
        return coerce_resolution_confidence(payload.get("confidence")) < LLM_STRONG_FALLBACK_CONFIDENCE

    def profile(self, state: PipelineState, column: ColumnProfile) -> dict[str, Any] | None:
        return self.profile_many(state, [column]).get(column.raw_name)

    def profile_many(self, state: PipelineState, columns: list[ColumnProfile]) -> dict[str, dict[str, Any]]:
        llm = self._client()
        if llm is None or not columns:
            return {}

        dataset_meta = require_dataset_meta(state)
        payload = self._invoke_json_payload(
            semantic_profile_batch_prompt(
                dataset_name=dataset_meta.dataset_name,
                provider_name=dataset_meta.provider_name,
                data_format=dataset_meta.data_format,
                columns=[
                    {
                        "raw_name": column.raw_name,
                        "normalized_name": column.normalized_name,
                        "semantic_tags": column.semantic_tags,
                        "inferred_type": column.inferred_primitive_type,
                        "sample_values": column.sample_values,
                        "top_values": column.top_values,
                    }
                    for column in columns
                ],
            ),
            system_prompt=SEMANTIC_PROFILE_SYSTEM_PROMPT,
        )
        if payload is None:
            return {}
        allowed_raw_names = {column.raw_name for column in columns}
        return self._sanitize_profiles(payload, allowed_raw_names)

    @staticmethod
    def _sanitize_profiles(
        payload: dict[str, Any],
        allowed_raw_names: set[str],
    ) -> dict[str, dict[str, Any]]:
        columns = payload.get("columns")
        if not isinstance(columns, list):
            return {}

        sanitized: dict[str, dict[str, Any]] = {}
        for item in columns:
            if not isinstance(item, dict):
                continue
            raw_name = str(item.get("raw_name") or "").strip()
            if not raw_name or raw_name not in allowed_raw_names or raw_name in sanitized:
                continue
            confidence = item.get("confidence")
            if confidence is None:
                item["confidence"] = LLM_SEMANTIC_PROFILE_CONFIDENCE_DEFAULT
            if item.get("label"):
                item["label"] = str(item["label"]).strip()
            if item.get("description"):
                item["description"] = str(item["description"]).strip()
            sanitized[raw_name] = item
        return sanitized
