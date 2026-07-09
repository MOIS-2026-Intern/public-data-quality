from __future__ import annotations

from typing import TYPE_CHECKING, Any

try:
    from ...core.config.constants import (
        LLM_RESOLUTION_CONFIDENCE,
        TAG_RULE_MAP,
        VALIDATION_CRITERIA,
    )
    from ...core.schema.models import ColumnProfile, PipelineState
    from ...core.validation.free_text import column_format_kind, looks_free_text_column
except ImportError:  # pragma: no cover
    if (__package__ or "").split(".", 1)[0] != "agents":
        raise
    from core.config.constants import (
        LLM_RESOLUTION_CONFIDENCE,
        TAG_RULE_MAP,
        VALIDATION_CRITERIA,
    )
    from core.schema.models import ColumnProfile, PipelineState
    from core.validation.free_text import column_format_kind, looks_free_text_column
from ..base import BaseAgent

if TYPE_CHECKING:
    from .llm_column_resolver import LLMColumnResolver


class LLMRoutingAgent(BaseAgent):
    name = "rule_router"
    NON_UNIQUE_NAME_TOKENS = (
        "명",
        "명칭",
        "이름",
        "기관",
        "부서",
        "담당",
        "경찰서",
        "시설",
        "업소",
        "주소",
        "소재지",
    )

    def __init__(self, column_resolver: "LLMColumnResolver | None" = None):
        self.column_resolver = column_resolver

    @staticmethod
    def _rule_tags(column: ColumnProfile) -> list[str]:
        if looks_free_text_column(column):
            return ["free_text"]

        tags = set(column.semantic_tags)
        name = f"{column.raw_name} {column.normalized_name}"
        if any(token in name for token in ("일자", "일시", "날짜", "년월", "등록일", "기준일")):
            tags.add("date")
        if any(token in name for token in ("주소", "소재지")):
            tags.add("address")
        if "위도" in name:
            tags.add("geo_lat")
        if "경도" in name:
            tags.add("geo_lon")
        if any(token in name for token in ("여부", "유무", "YN", "Yn", "yn", "Y/N")):
            tags.add("boolean")
        if any(token in name for token in ("구분", "유형", "종류", "상태", "분류")):
            tags.add("enum")
        if any(token in name for token in ("코드",)):
            tags.add("code")
        if any(token in name for token in ("명", "명칭", "이름", "기관명", "시설명", "경찰서명")):
            tags.add("name")
        if any(token in name for token in ("대수", "개수", "건수", "수량", "좌석수", "정원수")):
            tags.add("quantity")
        if any(token in name for token in ("폭", "너비")):
            tags.add("width")
        if any(token in name for token in ("전화", "연락처", "휴대전화")):
            tags.add("phone")
        return sorted(tags)

    @staticmethod
    def _allowed_rule_ids() -> set[str]:
        return {
            rule_id
            for category in VALIDATION_CRITERIA.values()
            for rule_id in category["criteria"].keys()
        }

    @staticmethod
    def _string_list(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]

    @classmethod
    def _looks_non_unique_name_column(cls, column: ColumnProfile) -> bool:
        name = f"{column.raw_name} {column.normalized_name}"
        return any(token in name for token in cls.NON_UNIQUE_NAME_TOKENS)

    @staticmethod
    def _confidence(value: Any) -> float:
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return LLM_RESOLUTION_CONFIDENCE

    def _apply_rule_fallback(self, column: ColumnProfile) -> ColumnProfile:
        rule_ids: list[str] = []
        rule_tags = self._rule_tags(column)
        if rule_tags:
            column.semantic_tags = list(dict.fromkeys(rule_tags))
        for tag in rule_tags:
            rule_ids.extend(TAG_RULE_MAP.get(tag, []))
        column.assigned_rules = list(dict.fromkeys(rule_ids))
        column.format_kind = column_format_kind(column)
        return column

    def _apply_rule_route(self, column: ColumnProfile) -> tuple[ColumnProfile, str]:
        return self._apply_rule_fallback(column), "rule_fallback"

    def _apply_llm_route(self, state: PipelineState, column: ColumnProfile, payload: dict[str, Any]) -> ColumnProfile:
        allowed_tags = set(TAG_RULE_MAP)
        allowed_rules = self._allowed_rule_ids()
        del state

        normalized_name = payload.get("normalized_name")
        if isinstance(normalized_name, str) and normalized_name.strip():
            column.normalized_name = normalized_name.strip()

        semantic_tags = [
            tag for tag in self._string_list(payload.get("semantic_tags"))
            if tag in allowed_tags
        ]
        if self._looks_non_unique_name_column(column):
            semantic_tags = [tag for tag in semantic_tags if tag != "identifier"]
            if "name" not in semantic_tags:
                semantic_tags.append("name")
        if semantic_tags:
            column.semantic_tags = list(dict.fromkeys(semantic_tags))

        assigned_rules = [
            rule_id for rule_id in self._string_list(payload.get("assigned_rules"))
            if rule_id in allowed_rules
        ]
        if looks_free_text_column(column):
            column.semantic_tags = ["free_text"]
            column.assigned_rules = []
            column.format_kind = "free_format"
            column.routing_confidence = max(column.routing_confidence, self._confidence(payload.get("confidence")))
            return column

        if self._looks_non_unique_name_column(column):
            assigned_rules = [
                rule_id
                for rule_id in assigned_rules
                if rule_id not in {"duplicate_data", "number_domain"}
            ]
        if not assigned_rules and column.semantic_tags:
            for tag in column.semantic_tags:
                assigned_rules.extend(TAG_RULE_MAP.get(tag, []))
        column.assigned_rules = list(dict.fromkeys(assigned_rules))
        column.format_kind = column_format_kind(column)

        column.routing_confidence = max(column.routing_confidence, self._confidence(payload.get("confidence")))
        return column

    def run(self, state: PipelineState) -> PipelineState:
        traces = list(state.get("agent_traces", []))
        updated: list[ColumnProfile] = []
        use_llm = (
            bool(state.get("use_llm_agents"))
            and self.column_resolver is not None
            and self.column_resolver.enabled
        )
        relationship_candidates: list[dict[str, Any]] | None = None

        for column in state["columns"]:
            column, route_source = self._apply_rule_route(column)
            llm_error = ""
            llm_model = ""
            llm_stage = ""
            llm_escalated = ""
            if use_llm:
                payload = self.column_resolver.resolve(state, column)
                if payload:
                    column = self._apply_llm_route(state, column, payload)
                    route_source = f"llm:{payload.get('_llm_stage', 'fast')}"
                    llm_model = str(payload.get("_llm_model", ""))
                    llm_stage = str(payload.get("_llm_stage", ""))
                    llm_escalated = str(payload.get("_llm_escalated", ""))
                else:
                    column = self._apply_rule_fallback(column)
                    llm_error = self.column_resolver.last_error
                    llm_model = getattr(self.column_resolver, "last_model_name", "")
                    llm_stage = getattr(self.column_resolver, "last_stage", "")

            traces.append(
                self.trace(
                    action="route_rules",
                    target=column.raw_name,
                    detail=(
                        f"source={route_source}, "
                        f"rules={column.assigned_rules}, "
                        f"confidence={column.routing_confidence:.2f}, "
                        f"model={llm_model}, stage={llm_stage}, escalated={llm_escalated}, "
                        f"llm_error={llm_error}"
                    ),
                )
            )
            updated.append(column)

        if use_llm:
            relationship_candidates = self.column_resolver.resolve_relationships(state, updated)
            traces.append(
                self.trace(
                    action="route_relationships",
                    detail=(
                        f"candidates={len(relationship_candidates)}, "
                        f"model={self.column_resolver.last_model_name}, "
                        f"stage={self.column_resolver.last_stage}, "
                        f"llm_error={self.column_resolver.last_error}"
                    ),
                )
            )

        traces.append(self.trace(action="routing_summary", detail=f"columns={len(updated)}"))
        result: PipelineState = {
            "columns": updated,
            "agent_traces": traces,
        }
        if relationship_candidates is not None:
            result["relationship_candidates"] = relationship_candidates
        return result
