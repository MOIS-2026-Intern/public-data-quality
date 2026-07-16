from __future__ import annotations

from typing import Any

from backend.application.shared import parse_json_content
from backend.application.dto import PipelineState, pipeline_data, require_dataset_meta
from backend.application.ports import JsonLLMPort
from backend.application.prompts.resolution import (
    RELATIONSHIP_ROUTING_SYSTEM_PROMPT,
    SCHEMA_ROUTING_SYSTEM_PROMPT,
    relationship_routing_prompt,
    schema_routing_batch_prompt,
)
from backend.config.llm import LLM_STRONG_FALLBACK_CONFIDENCE
from backend.config.validation import TAG_RULE_MAP, VALIDATION_CRITERIA
from backend.domain.entities.models import ColumnProfile
from backend.domain.policies.relationships.common import is_non_unique_local_admin_reference_pair
from .confidence import coerce_resolution_confidence
from .prompt_payload import compact_column_payload


_RELATIONSHIP_RULE_IDS = {
    "time_sequence_consistency",
    "precedence_accuracy",
    "logical_consistency",
    "calculation_formula",
    "reference_relation",
}
_RELATIONSHIP_TAGS = {
    "address",
    "amount",
    "boolean",
    "code",
    "coordinate_pair",
    "count",
    "date",
    "enum",
    "geo_lat",
    "geo_lon",
    "identifier",
    "numeric",
    "quantity",
    "rate",
}
_RELATIONSHIP_LABEL_TAGS = {"name"}
_REFERENCE_DRIVER_TAGS = {"code", "coordinate_pair", "enum", "identifier"}
_RELATIONSHIP_NAME_TOKENS = (
    "주소",
    "지역",
    "시도",
    "일자",
    "날짜",
    "시작",
    "종료",
    "합계",
    "총",
    "계",
    "건수",
    "수량",
    "금액",
    "코드",
    "번호",
    "여부",
    "위도",
    "경도",
)
_RELATIONSHIP_LABEL_NAME_TOKENS = ("명", "명칭", "이름")


def _relationship_target_columns(columns: list[ColumnProfile]) -> list[ColumnProfile]:
    selected = []
    labels = []
    has_reference_driver = False
    for column in columns:
        name = f"{column.raw_name} {column.normalized_name}"
        if _RELATIONSHIP_RULE_IDS.intersection(column.assigned_rules):
            selected.append(column)
            if _REFERENCE_DRIVER_TAGS.intersection(column.semantic_tags) or any(token in name for token in ("코드", "번호")):
                has_reference_driver = True
            continue
        if _RELATIONSHIP_TAGS.intersection(column.semantic_tags):
            selected.append(column)
            if _REFERENCE_DRIVER_TAGS.intersection(column.semantic_tags):
                has_reference_driver = True
            continue
        if any(token in name for token in _RELATIONSHIP_NAME_TOKENS):
            selected.append(column)
            if any(token in name for token in ("코드", "번호", "구분", "분류", "유형")):
                has_reference_driver = True
            continue
        if _RELATIONSHIP_LABEL_TAGS.intersection(column.semantic_tags) or any(
            token in name for token in _RELATIONSHIP_LABEL_NAME_TOKENS
        ):
            labels.append(column)
    if has_reference_driver:
        selected.extend(labels)
    deduped: list[ColumnProfile] = []
    seen: set[str] = set()
    for column in selected:
        if column.raw_name in seen:
            continue
        seen.add(column.raw_name)
        deduped.append(column)
    return deduped


class LLMColumnResolver:
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
        difficult: Any,
    ) -> dict[str, Any] | None:
        fast_payload = self._invoke_json_payload_once(
            self._llm,
            "fast",
            prompt,
            system_prompt=system_prompt,
        )
        if fast_payload is not None and not difficult(fast_payload):
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
    def _list_payload(value: Any) -> list[Any]:
        return value if isinstance(value, list) else []

    @classmethod
    def _routing_needs_strong(cls, payload: dict[str, Any]) -> bool:
        confidence = coerce_resolution_confidence(payload.get("confidence"))
        if confidence < LLM_STRONG_FALLBACK_CONFIDENCE:
            return True
        if not cls._list_payload(payload.get("assigned_rules")) and not cls._list_payload(payload.get("semantic_tags")):
            return True
        return False

    @classmethod
    def _routing_batch_needs_strong(cls, payload: dict[str, Any]) -> bool:
        columns = payload.get("columns")
        if not isinstance(columns, list) or not columns:
            return True
        return any(not isinstance(column_payload, dict) or cls._routing_needs_strong(column_payload) for column_payload in columns)

    @staticmethod
    def _relationship_needs_strong(payload: dict[str, Any]) -> bool:
        candidates = payload.get("relationship_candidates")
        if not isinstance(candidates, list):
            return True
        if not candidates:
            return False
        confidences = [
            coerce_resolution_confidence(candidate.get("confidence"))
            for candidate in candidates
            if isinstance(candidate, dict)
        ]
        return bool(confidences) and max(confidences) < LLM_STRONG_FALLBACK_CONFIDENCE

    def resolve(self, state: PipelineState, column: ColumnProfile) -> dict[str, Any] | None:
        return self.resolve_many(state, [column]).get(column.raw_name)

    def resolve_many(self, state: PipelineState, columns: list[ColumnProfile]) -> dict[str, dict[str, Any]]:
        llm = self._client()
        if llm is None or not columns:
            return {}

        dataset_meta = require_dataset_meta(state)
        data = pipeline_data(state)
        allowed_tags = sorted(TAG_RULE_MAP.keys())
        allowed_rules = sorted(
            {
                rule_id
                for category in VALIDATION_CRITERIA.values()
                for rule_id in category["criteria"].keys()
            }
        )
        all_columns = [candidate.raw_name for candidate in data.columns]
        fast_payload = self._invoke_json_payload_once(
            llm,
            "fast",
            schema_routing_batch_prompt(
                dataset_name=dataset_meta.dataset_name,
                provider_name=dataset_meta.provider_name,
                keywords=dataset_meta.keywords,
                data_format=dataset_meta.data_format,
                all_columns=all_columns,
                columns=[
                    compact_column_payload(column, include_routing_fields=True)
                    for column in columns
                ],
                allowed_tags=allowed_tags,
                allowed_rules=allowed_rules,
            ),
            system_prompt=SCHEMA_ROUTING_SYSTEM_PROMPT,
        )
        allowed_raw_names = {column.raw_name for column in columns}
        resolved = self._sanitize_routing_payloads(fast_payload, allowed_raw_names) if fast_payload is not None else {}
        strong_columns = [
            column
            for column in columns
            if column.raw_name not in resolved or self._routing_needs_strong(resolved[column.raw_name])
        ]
        if not strong_columns or not self._strong_enabled:
            return resolved

        strong_payload = self._invoke_json_payload_once(
            self._strong_llm,
            "strong",
            schema_routing_batch_prompt(
                dataset_name=dataset_meta.dataset_name,
                provider_name=dataset_meta.provider_name,
                keywords=dataset_meta.keywords,
                data_format=dataset_meta.data_format,
                all_columns=all_columns,
                columns=[
                    compact_column_payload(column, include_routing_fields=True)
                    for column in strong_columns
                ],
                allowed_tags=allowed_tags,
                allowed_rules=allowed_rules,
            ),
            system_prompt=SCHEMA_ROUTING_SYSTEM_PROMPT,
        )
        if strong_payload is None:
            return resolved

        strong_results = self._sanitize_routing_payloads(strong_payload, {column.raw_name for column in strong_columns})
        for raw_name, payload in strong_results.items():
            payload["_llm_escalated"] = True
            if raw_name in resolved:
                payload["_llm_fast_confidence"] = resolved[raw_name].get("confidence")
        resolved.update(strong_results)
        return resolved

    @staticmethod
    def _sanitize_routing_payloads(
        payload: dict[str, Any] | None,
        allowed_raw_names: set[str],
    ) -> dict[str, dict[str, Any]]:
        if payload is None:
            return {}
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
            item["_llm_model"] = payload.get("_llm_model", "")
            item["_llm_stage"] = payload.get("_llm_stage", "")
            item["_llm_escalated"] = bool(payload.get("_llm_escalated"))
            sanitized[raw_name] = item
        return sanitized

    def resolve_relationships(self, state: PipelineState, columns: list[ColumnProfile]) -> list[dict[str, Any]]:
        llm = self._client()
        if llm is None:
            return []
        target_columns = _relationship_target_columns(columns)
        if len(target_columns) < 2:
            self.last_error = ""
            self.last_response_preview = ""
            return []

        dataset_meta = require_dataset_meta(state)
        allowed_rules = [
            "time_sequence_consistency",
            "precedence_accuracy",
            "logical_consistency",
            "calculation_formula",
            "reference_relation",
        ]
        column_payload = [
            compact_column_payload(column, include_semantic_fields=True)
            for column in target_columns
        ]
        payload = self._invoke_json_payload(
            relationship_routing_prompt(
                dataset_name=dataset_meta.dataset_name,
                provider_name=dataset_meta.provider_name,
                keywords=dataset_meta.keywords,
                data_format=dataset_meta.data_format,
                columns=column_payload,
                allowed_rules=allowed_rules,
            ),
            system_prompt=RELATIONSHIP_ROUTING_SYSTEM_PROMPT,
            difficult=self._relationship_needs_strong,
        )
        if payload is None:
            return []

        by_name = {column.raw_name: column for column in target_columns}
        raw_names = set(by_name)
        candidates = payload.get("relationship_candidates")
        if not isinstance(candidates, list):
            return []

        sanitized: list[dict[str, Any]] = []
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            rule_id = str(candidate.get("rule_id") or "").strip()
            if rule_id not in allowed_rules:
                continue
            candidate_columns = [
                str(name).strip()
                for name in candidate.get("columns", [])
                if str(name).strip() in raw_names
            ]
            candidate_columns = list(dict.fromkeys(candidate_columns))
            if len(candidate_columns) < 2:
                continue
            if rule_id == "reference_relation" and len(candidate_columns) != 2:
                continue
            resolved_columns = [by_name[name] for name in candidate_columns]
            if rule_id == "reference_relation" and is_non_unique_local_admin_reference_pair(
                resolved_columns[0],
                resolved_columns[1],
            ):
                continue
            sanitized.append(
                {
                    "rule_id": rule_id,
                    "columns": candidate_columns,
                    "confidence": coerce_resolution_confidence(candidate.get("confidence")),
                    "reason": str(candidate.get("reason") or "").strip(),
                }
            )
        return sanitized
