from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.application.agents.routing import LLMRoutingAgent
from backend.application.agents.semantic_profiling import SemanticProfilingAgent
from backend.application.services.resolution import LLMColumnResolver, LLMSemanticProfiler
from backend.domain.entities.models import ColumnProfile, DatasetMeta


def _column(name: str) -> ColumnProfile:
    return ColumnProfile(
        raw_name=name,
        normalized_name=name,
        source="response",
        semantic_tags=[],
        assigned_rules=[],
        sample_values=["서울특별시", "부산광역시"],
        top_values=[("서울특별시", 1)],
        inferred_primitive_type="string",
        distinct_count=2,
        non_empty_count=2,
    )


class FakeBatchResolver:
    enabled = True
    last_error = ""
    last_response_preview = ""
    last_model_name = "fake-fast"
    last_stage = "fast"

    def __init__(self) -> None:
        self.resolve_many_calls = 0
        self.relationship_calls = 0

    def resolve_many(self, state, columns):
        self.resolve_many_calls += 1
        return {
            column.raw_name: {
                "raw_name": column.raw_name,
                "normalized_name": column.normalized_name,
                "semantic_tags": ["name"],
                "assigned_rules": ["required_value"],
                "confidence": 0.93,
                "reason": "기관명 계열 컬럼입니다.",
                "_llm_model": "fake-fast",
                "_llm_stage": "fast",
                "_llm_escalated": False,
            }
            for column in columns
        }

    def resolve_relationships(self, state, columns):
        self.relationship_calls += 1
        return []


class FakeBatchSemanticProfiler:
    enabled = True
    last_error = ""
    last_response_preview = ""
    last_model_name = "fake-fast"
    last_stage = "fast"

    def __init__(self) -> None:
        self.profile_many_calls = 0

    def profile_many(self, state, columns):
        self.profile_many_calls += 1
        return {
            column.raw_name: {
                "raw_name": column.raw_name,
                "label": "기관 명칭",
                "description": "공공데이터에 포함된 기관 또는 대상 명칭입니다.",
                "confidence": 0.92,
                "_llm_model": "fake-fast",
                "_llm_stage": "fast",
                "_llm_escalated": False,
            }
            for column in columns
        }


class FakeLLMResponse:
    def __init__(self, content: str) -> None:
        self.content = content


class FakeRelationshipLLM:
    model_name = "fake-fast"
    last_error = ""
    last_response_preview = ""

    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls = 0
        self.prompts: list[str] = []

    @property
    def enabled(self) -> bool:
        return True

    def invoke_json(self, prompt: str, *, system_prompt: str | None = None) -> FakeLLMResponse | None:
        self.calls += 1
        self.prompts.append(prompt)
        return FakeLLMResponse(json.dumps(self.payload, ensure_ascii=False))


class FakeRoutingLLM(FakeRelationshipLLM):
    pass


def test_routing_agent_batches_llm_resolution() -> None:
    resolver = FakeBatchResolver()
    columns = [_column("기관"), _column("시설")]

    result = LLMRoutingAgent(column_resolver=resolver).run(
        {
            "use_llm_agents": True,
            "dataset_meta": DatasetMeta(dataset_id="d", dataset_name="테스트", provider_name="기관"),
            "columns": columns,
            "agent_traces": [],
        }
    )

    assert resolver.resolve_many_calls == 1
    assert resolver.relationship_calls == 1
    assert all(column.assigned_rules == ["required_value"] for column in result["columns"])
    assert all(column.semantic_tags == ["name"] for column in result["columns"])


def test_routing_agent_skips_llm_resolution_for_clear_local_routes() -> None:
    resolver = FakeBatchResolver()
    columns = [_column("기관명"), _column("시설명")]

    result = LLMRoutingAgent(column_resolver=resolver).run(
        {
            "use_llm_agents": True,
            "dataset_meta": DatasetMeta(dataset_id="d", dataset_name="테스트", provider_name="기관"),
            "columns": columns,
            "agent_traces": [],
        }
    )

    assert resolver.resolve_many_calls == 0
    assert resolver.relationship_calls == 1
    assert all("required_value" in column.assigned_rules for column in result["columns"])
    assert all(column.semantic_tags == ["name"] for column in result["columns"])


def test_semantic_profiling_agent_batches_llm_profiles() -> None:
    profiler = FakeBatchSemanticProfiler()
    columns = [_column("기관"), _column("시설")]

    result = SemanticProfilingAgent(semantic_profiler=profiler).run(
        {
            "use_llm_agents": True,
            "columns": columns,
            "agent_traces": [],
        }
    )

    assert profiler.profile_many_calls == 1
    assert all(column.semantic_profile_label == "기관 명칭" for column in result["columns"])
    assert all(column.semantic_profile_confidence == 0.92 for column in result["columns"])


def test_column_resolver_escalates_only_low_confidence_columns_to_strong() -> None:
    fast_llm = FakeRoutingLLM(
        {
            "columns": [
                {
                    "raw_name": "명확컬럼",
                    "normalized_name": "명확컬럼",
                    "semantic_tags": ["name"],
                    "assigned_rules": ["required_value"],
                    "confidence": 0.95,
                    "reason": "명확합니다.",
                },
                {
                    "raw_name": "애매컬럼",
                    "normalized_name": "애매컬럼",
                    "semantic_tags": [],
                    "assigned_rules": [],
                    "confidence": 0.30,
                    "reason": "애매합니다.",
                },
            ]
        }
    )
    strong_llm = FakeRoutingLLM(
        {
            "columns": [
                {
                    "raw_name": "애매컬럼",
                    "normalized_name": "애매컬럼",
                    "semantic_tags": ["name"],
                    "assigned_rules": ["required_value"],
                    "confidence": 0.97,
                    "reason": "정밀 검증 결과 명칭 컬럼입니다.",
                }
            ]
        }
    )
    strong_llm.model_name = "fake-strong"
    resolver = LLMColumnResolver(fast_llm=fast_llm, strong_llm=strong_llm)

    resolved = resolver.resolve_many(
        {
            "dataset_meta": DatasetMeta(dataset_id="d", dataset_name="테스트", provider_name="기관"),
            "columns": [_column("명확컬럼"), _column("애매컬럼")],
        },
        [_column("명확컬럼"), _column("애매컬럼")],
    )

    assert fast_llm.calls == 1
    assert strong_llm.calls == 1
    assert "애매컬럼" in strong_llm.prompts[0]
    assert strong_llm.prompts[0].count("명확컬럼") == 1
    assert strong_llm.prompts[0].count("애매컬럼") > 1
    assert resolved["명확컬럼"]["_llm_stage"] == "fast"
    assert resolved["애매컬럼"]["_llm_stage"] == "strong"
    assert resolved["애매컬럼"]["_llm_escalated"] is True


def test_semantic_profiler_escalates_only_low_confidence_columns_to_strong() -> None:
    fast_llm = FakeRoutingLLM(
        {
            "columns": [
                {
                    "raw_name": "명확컬럼",
                    "label": "명확 컬럼",
                    "description": "의미가 명확한 컬럼입니다.",
                    "confidence": 0.94,
                },
                {
                    "raw_name": "애매컬럼",
                    "label": "애매 컬럼",
                    "description": "의미가 애매한 컬럼입니다.",
                    "confidence": 0.20,
                },
            ]
        }
    )
    strong_llm = FakeRoutingLLM(
        {
            "columns": [
                {
                    "raw_name": "애매컬럼",
                    "label": "정밀 컬럼",
                    "description": "정밀 검증으로 보완한 컬럼입니다.",
                    "confidence": 0.96,
                }
            ]
        }
    )
    strong_llm.model_name = "fake-strong"
    profiler = LLMSemanticProfiler(fast_llm=fast_llm, strong_llm=strong_llm)

    profiles = profiler.profile_many(
        {
            "dataset_meta": DatasetMeta(dataset_id="d", dataset_name="테스트", provider_name="기관"),
            "columns": [_column("명확컬럼"), _column("애매컬럼")],
        },
        [_column("명확컬럼"), _column("애매컬럼")],
    )

    assert fast_llm.calls == 1
    assert strong_llm.calls == 1
    assert "애매컬럼" in strong_llm.prompts[0]
    assert "명확컬럼" not in strong_llm.prompts[0]
    assert profiles["명확컬럼"]["_llm_stage"] == "fast"
    assert profiles["애매컬럼"]["_llm_stage"] == "strong"
    assert profiles["애매컬럼"]["_llm_escalated"] is True


def test_column_resolver_filters_plain_sigungu_reference_relationships() -> None:
    columns = [
        ColumnProfile(
            raw_name="시군구",
            normalized_name="시군구",
            source="response",
            semantic_tags=["code"],
            assigned_rules=["reference_relation"],
            sample_values=["380"],
            top_values=[("380", 2)],
            inferred_primitive_type="string",
            distinct_count=1,
            non_empty_count=2,
        ),
        ColumnProfile(
            raw_name="시군구명",
            normalized_name="시군구명",
            source="response",
            semantic_tags=["name"],
            assigned_rules=["reference_relation"],
            sample_values=["사하구", "은평구"],
            top_values=[("사하구", 1), ("은평구", 1)],
            inferred_primitive_type="string",
            distinct_count=2,
            non_empty_count=2,
        ),
    ]
    resolver = LLMColumnResolver(
        fast_llm=FakeRelationshipLLM(
            {
                "relationship_candidates": [
                    {
                        "rule_id": "reference_relation",
                        "columns": ["시군구", "시군구명"],
                        "confidence": 0.99,
                        "reason": "코드와 명칭 대응으로 보입니다.",
                    }
                ]
            }
        )
    )

    resolved = resolver.resolve_relationships(
        {
            "dataset_meta": DatasetMeta(dataset_id="d", dataset_name="테스트", provider_name="기관"),
            "columns": columns,
        },
        columns,
    )

    assert resolved == []


def test_column_resolver_skips_relationship_llm_without_relationship_targets() -> None:
    columns = [
        ColumnProfile(
            raw_name="비고",
            normalized_name="비고",
            source="response",
            semantic_tags=["free_text"],
            assigned_rules=[],
            sample_values=["참고 사항"],
            top_values=[("참고 사항", 1)],
            inferred_primitive_type="string",
            distinct_count=1,
            non_empty_count=1,
        )
    ]
    llm = FakeRelationshipLLM({"relationship_candidates": []})
    resolver = LLMColumnResolver(fast_llm=llm)

    resolved = resolver.resolve_relationships(
        {
            "dataset_meta": DatasetMeta(dataset_id="d", dataset_name="테스트", provider_name="기관"),
            "columns": columns,
        },
        columns,
    )

    assert resolved == []
    assert llm.calls == 0


def test_column_resolver_filters_plain_eupmyeondong_reference_relationships() -> None:
    columns = [
        ColumnProfile(
            raw_name="읍면동",
            normalized_name="읍면동",
            source="response",
            semantic_tags=["code"],
            assigned_rules=["reference_relation"],
            sample_values=["602"],
            top_values=[("602", 2)],
            inferred_primitive_type="string",
            distinct_count=1,
            non_empty_count=2,
        ),
        ColumnProfile(
            raw_name="읍면동명",
            normalized_name="읍면동명",
            source="response",
            semantic_tags=["name"],
            assigned_rules=["reference_relation"],
            sample_values=["상계동", "중계동"],
            top_values=[("상계동", 1), ("중계동", 1)],
            inferred_primitive_type="string",
            distinct_count=2,
            non_empty_count=2,
        ),
    ]
    resolver = LLMColumnResolver(
        fast_llm=FakeRelationshipLLM(
            {
                "relationship_candidates": [
                    {
                        "rule_id": "reference_relation",
                        "columns": ["읍면동", "읍면동명"],
                        "confidence": 0.99,
                        "reason": "코드와 명칭 대응으로 보입니다.",
                    }
                ]
            }
        )
    )

    resolved = resolver.resolve_relationships(
        {
            "dataset_meta": DatasetMeta(dataset_id="d", dataset_name="테스트", provider_name="기관"),
            "columns": columns,
        },
        columns,
    )

    assert resolved == []


def test_column_resolver_filters_plain_beopjeongdong_reference_relationships() -> None:
    columns = [
        ColumnProfile(
            raw_name="법정동",
            normalized_name="법정동",
            source="response",
            semantic_tags=["code"],
            assigned_rules=["reference_relation"],
            sample_values=["110"],
            top_values=[("110", 2)],
            inferred_primitive_type="string",
            distinct_count=1,
            non_empty_count=2,
        ),
        ColumnProfile(
            raw_name="법정동명",
            normalized_name="법정동명",
            source="response",
            semantic_tags=["name"],
            assigned_rules=["reference_relation"],
            sample_values=["청운동", "효자동"],
            top_values=[("청운동", 1), ("효자동", 1)],
            inferred_primitive_type="string",
            distinct_count=2,
            non_empty_count=2,
        ),
    ]
    resolver = LLMColumnResolver(
        fast_llm=FakeRelationshipLLM(
            {
                "relationship_candidates": [
                    {
                        "rule_id": "reference_relation",
                        "columns": ["법정동", "법정동명"],
                        "confidence": 0.99,
                        "reason": "코드와 명칭 대응으로 보입니다.",
                    }
                ]
            }
        )
    )

    resolved = resolver.resolve_relationships(
        {
            "dataset_meta": DatasetMeta(dataset_id="d", dataset_name="테스트", provider_name="기관"),
            "columns": columns,
        },
        columns,
    )

    assert resolved == []


def test_column_resolver_filters_local_admin_code_name_variants() -> None:
    columns = [
        ColumnProfile(
            raw_name="행정동코드",
            normalized_name="행정동코드",
            source="response",
            semantic_tags=["code"],
            assigned_rules=["reference_relation"],
            sample_values=["101"],
            top_values=[("101", 2)],
            inferred_primitive_type="string",
            distinct_count=1,
            non_empty_count=2,
        ),
        ColumnProfile(
            raw_name="행정동명칭",
            normalized_name="행정동명칭",
            source="response",
            semantic_tags=["name"],
            assigned_rules=["reference_relation"],
            sample_values=["충무로동", "을지로동"],
            top_values=[("충무로동", 1), ("을지로동", 1)],
            inferred_primitive_type="string",
            distinct_count=2,
            non_empty_count=2,
        ),
    ]
    resolver = LLMColumnResolver(
        fast_llm=FakeRelationshipLLM(
            {
                "relationship_candidates": [
                    {
                        "rule_id": "reference_relation",
                        "columns": ["행정동코드", "행정동명칭"],
                        "confidence": 0.99,
                        "reason": "코드와 명칭 대응으로 보입니다.",
                    }
                ]
            }
        )
    )

    resolved = resolver.resolve_relationships(
        {
            "dataset_meta": DatasetMeta(dataset_id="d", dataset_name="테스트", provider_name="기관"),
            "columns": columns,
        },
        columns,
    )

    assert resolved == []


def test_column_resolver_keeps_long_official_local_admin_code_relationships() -> None:
    columns = [
        ColumnProfile(
            raw_name="행정동코드",
            normalized_name="행정동코드",
            source="response",
            semantic_tags=["code"],
            assigned_rules=["reference_relation"],
            sample_values=["1114012300"],
            top_values=[("1114012300", 2)],
            inferred_primitive_type="string",
            distinct_count=1,
            non_empty_count=2,
        ),
        ColumnProfile(
            raw_name="행정동명",
            normalized_name="행정동명",
            source="response",
            semantic_tags=["name"],
            assigned_rules=["reference_relation"],
            sample_values=["충무로동", "을지로동"],
            top_values=[("충무로동", 1), ("을지로동", 1)],
            inferred_primitive_type="string",
            distinct_count=2,
            non_empty_count=2,
        ),
    ]
    resolver = LLMColumnResolver(
        fast_llm=FakeRelationshipLLM(
            {
                "relationship_candidates": [
                    {
                        "rule_id": "reference_relation",
                        "columns": ["행정동코드", "행정동명"],
                        "confidence": 0.99,
                        "reason": "코드와 명칭 대응으로 보입니다.",
                    }
                ]
            }
        )
    )

    resolved = resolver.resolve_relationships(
        {
            "dataset_meta": DatasetMeta(dataset_id="d", dataset_name="테스트", provider_name="기관"),
            "columns": columns,
        },
        columns,
    )

    assert resolved == [
        {
            "rule_id": "reference_relation",
            "columns": ["행정동코드", "행정동명"],
            "confidence": 0.99,
            "reason": "코드와 명칭 대응으로 보입니다.",
        }
    ]


def test_column_resolver_drops_three_column_reference_candidates() -> None:
    columns = [
        ColumnProfile(
            raw_name="기관코드",
            normalized_name="기관코드",
            source="response",
            semantic_tags=["code"],
            assigned_rules=["reference_relation"],
            sample_values=["A-01"],
            top_values=[("A-01", 2)],
            inferred_primitive_type="string",
            distinct_count=1,
            non_empty_count=2,
        ),
        ColumnProfile(
            raw_name="기관명",
            normalized_name="기관명",
            source="response",
            semantic_tags=["name"],
            assigned_rules=["reference_relation"],
            sample_values=["기관A", "기관B"],
            top_values=[("기관A", 1), ("기관B", 1)],
            inferred_primitive_type="string",
            distinct_count=2,
            non_empty_count=2,
        ),
        ColumnProfile(
            raw_name="기관유형",
            normalized_name="기관유형",
            source="response",
            semantic_tags=["enum"],
            assigned_rules=[],
            sample_values=["공공"],
            top_values=[("공공", 2)],
            inferred_primitive_type="string",
            distinct_count=1,
            non_empty_count=2,
        ),
    ]
    resolver = LLMColumnResolver(
        fast_llm=FakeRelationshipLLM(
            {
                "relationship_candidates": [
                    {
                        "rule_id": "reference_relation",
                        "columns": ["기관코드", "기관명", "기관유형"],
                        "confidence": 0.99,
                        "reason": "세 컬럼이 함께 보입니다.",
                    }
                ]
            }
        )
    )

    resolved = resolver.resolve_relationships(
        {
            "dataset_meta": DatasetMeta(dataset_id="d", dataset_name="테스트", provider_name="기관"),
            "columns": columns,
        },
        columns,
    )

    assert resolved == []
