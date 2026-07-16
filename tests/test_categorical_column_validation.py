from collections import Counter
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.application.services.categorical_validation.value_validator import LLMCategoricalValueValidator
from backend.application.services.categorical_validation.column_validation import (
    is_candidate_column,
    llm_skip_reason,
    validation_values,
)
from backend.config.categorical import CATEGORICAL_LLM_MAX_DISTINCT, CATEGORICAL_LLM_MAX_VALUES
from backend.domain.entities.models import ColumnProfile


def _categorical_column(*, distinct_count: int) -> ColumnProfile:
    return ColumnProfile(
        raw_name="구분",
        normalized_name="구분",
        source="response",
        semantic_tags=["enum"],
        distinct_count=distinct_count,
        top_values=[("값0", 100)],
    )


def _column(
    *,
    raw_name: str,
    semantic_tags: list[str],
    distinct_count: int,
    non_empty_count: int | None = None,
    sample_values: list[str] | None = None,
) -> ColumnProfile:
    return ColumnProfile(
        raw_name=raw_name,
        normalized_name=raw_name,
        source="response",
        semantic_tags=semantic_tags,
        distinct_count=distinct_count,
        non_empty_count=non_empty_count,
        top_values=[("값0", 100)],
        sample_values=sample_values or ["값0", "값1"],
        inferred_primitive_type="string",
    )


def test_categorical_llm_candidate_allows_more_than_thirty_distinct_values() -> None:
    column = _categorical_column(distinct_count=45)
    counter = Counter({f"값{index}": index + 1 for index in range(45)})

    assert is_candidate_column(column) is True
    assert llm_skip_reason(column, counter) is None


def test_categorical_llm_skips_free_text_columns() -> None:
    column = _column(
        raw_name="내용",
        semantic_tags=["free_text"],
        distinct_count=3,
        sample_values=["상세 설명입니다.", "긴 민원 내용입니다."],
    )
    counter = Counter({"상세 설명입니다.": 2, "긴 민원 내용입니다.": 1})

    assert is_candidate_column(column) is False
    assert llm_skip_reason(column, counter) == "free_text"


def test_categorical_llm_skips_deterministic_semantic_tags_even_with_name_tokens() -> None:
    column = _column(raw_name="데이터기준일자", semantic_tags=["date"], distinct_count=2)
    counter = Counter({"2026-01-01": 9, "2026-01-02": 1})

    assert is_candidate_column(column) is False
    assert llm_skip_reason(column, counter) == "deterministic_semantic_tag"


def test_categorical_llm_skips_high_cardinality_columns() -> None:
    column = _column(raw_name="시설명", semantic_tags=["name"], distinct_count=CATEGORICAL_LLM_MAX_DISTINCT + 1)
    counter = Counter({f"시설{index}": 1 for index in range(CATEGORICAL_LLM_MAX_DISTINCT + 1)})

    assert is_candidate_column(column) is True
    assert llm_skip_reason(column, counter) == f"distinct_count>{CATEGORICAL_LLM_MAX_DISTINCT}"


def test_categorical_llm_skips_high_distinct_ratio_columns() -> None:
    column = _column(raw_name="시설명", semantic_tags=["name"], distinct_count=20)
    counter = Counter({f"시설{index}": 1 for index in range(20)})

    assert is_candidate_column(column) is True
    assert llm_skip_reason(column, counter) == "distinct_ratio>0.15"


def test_categorical_validation_values_keep_common_and_rare_values_when_limited() -> None:
    counter = Counter(
        {
            **{f"상위값{index}": 100 - index for index in range(40)},
            **{f"희귀값{index}": 1 for index in range(40)},
        }
    )

    values = validation_values(counter)
    names = {item["value"] for item in values}

    assert len(values) == CATEGORICAL_LLM_MAX_VALUES
    assert "상위값0" in names
    assert "희귀값0" in names


class _FakeLLMResponse:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeJsonLLM:
    enabled = True
    last_error = ""
    last_response_preview = ""

    def __init__(self, *, model_name: str, payload: dict) -> None:
        self.model_name = model_name
        self.payload = payload
        self.calls = 0

    def invoke_json(self, prompt: str, *, system_prompt: str | None = None) -> _FakeLLMResponse:
        self.calls += 1
        content = json.dumps(self.payload, ensure_ascii=False)
        self.last_response_preview = content[:300]
        return _FakeLLMResponse(content)


def test_categorical_value_validation_uses_fast_model_when_no_review_items() -> None:
    fast_llm = _FakeJsonLLM(
        model_name="fast",
        payload={"domain_label": "범주", "overall_confidence": 0.95},
    )
    strong_llm = _FakeJsonLLM(
        model_name="strong",
        payload={"domain_label": "범주", "overall_confidence": 0.95},
    )

    result = LLMCategoricalValueValidator(fast_llm=fast_llm, strong_llm=strong_llm).validate(
        dataset_name="테스트",
        provider_name="기관",
        column_name="구분",
        standard_candidate=None,
        semantic_tags=["enum"],
        format_kind="fixed_format",
        values=[{"value": "정상", "count": 10}],
    )

    assert result["_llm_stage"] == "fast"
    assert fast_llm.calls == 1
    assert strong_llm.calls == 0


def test_categorical_value_validation_does_not_escalate_low_confidence_review_items() -> None:
    fast_llm = _FakeJsonLLM(
        model_name="fast",
        payload={
            "domain_label": "범주",
            "overall_confidence": 0.7,
            "out_of_domain_values": [{"value": "이상값", "confidence": 0.8}],
        },
    )
    strong_llm = _FakeJsonLLM(
        model_name="strong",
        payload={"domain_label": "범주", "overall_confidence": 0.95},
    )

    result = LLMCategoricalValueValidator(fast_llm=fast_llm, strong_llm=strong_llm).validate(
        dataset_name="테스트",
        provider_name="기관",
        column_name="구분",
        standard_candidate=None,
        semantic_tags=["enum"],
        format_kind="fixed_format",
        values=[{"value": "이상값", "count": 1}],
    )

    assert result["_llm_stage"] == "fast"
    assert result["_llm_escalated"] is False
    assert fast_llm.calls == 1
    assert strong_llm.calls == 0


def test_categorical_value_validation_escalates_high_confidence_review_items_to_strong_model() -> None:
    fast_llm = _FakeJsonLLM(
        model_name="fast",
        payload={
            "domain_label": "범주",
            "overall_confidence": 0.95,
            "out_of_domain_values": [{"value": "이상값", "confidence": 0.95}],
        },
    )
    strong_llm = _FakeJsonLLM(
        model_name="strong",
        payload={"domain_label": "범주", "overall_confidence": 0.95},
    )

    result = LLMCategoricalValueValidator(fast_llm=fast_llm, strong_llm=strong_llm).validate(
        dataset_name="테스트",
        provider_name="기관",
        column_name="구분",
        standard_candidate=None,
        semantic_tags=["enum"],
        format_kind="fixed_format",
        values=[{"value": "이상값", "count": 1}],
    )

    assert result["_llm_stage"] == "strong"
    assert result["_llm_escalated"] is True
    assert fast_llm.calls == 1
    assert strong_llm.calls == 1


def test_row_context_validation_uses_fast_model_when_no_issues() -> None:
    fast_llm = _FakeJsonLLM(
        model_name="fast",
        payload={"row_context_issues": [], "overall_confidence": 0.2},
    )
    strong_llm = _FakeJsonLLM(
        model_name="strong",
        payload={"row_context_issues": [], "overall_confidence": 0.2},
    )

    result = LLMCategoricalValueValidator(fast_llm=fast_llm, strong_llm=strong_llm).validate_row_context(
        dataset_name="테스트",
        provider_name="기관",
        columns=[{"raw_name": "구분", "normalized_name": "구분"}],
        rows=[{"구분": "정상"}],
    )

    assert result["_llm_stage"] == "fast"
    assert fast_llm.calls == 1
    assert strong_llm.calls == 0


def test_address_detail_validation_uses_fast_model_when_no_issues() -> None:
    fast_llm = _FakeJsonLLM(
        model_name="fast",
        payload={"address_detail_issues": [], "overall_confidence": 0.2},
    )
    strong_llm = _FakeJsonLLM(
        model_name="strong",
        payload={"address_detail_issues": [], "overall_confidence": 0.2},
    )

    result = LLMCategoricalValueValidator(fast_llm=fast_llm, strong_llm=strong_llm).validate_address_detail_candidates(
        dataset_name="테스트",
        provider_name="기관",
        column_name="상세주소",
        related_columns=["주소"],
        candidates=[{"row_index": 1, "column_name": "상세주소", "value": "2층"}],
    )

    assert result["_llm_stage"] == "fast"
    assert fast_llm.calls == 1
    assert strong_llm.calls == 0
