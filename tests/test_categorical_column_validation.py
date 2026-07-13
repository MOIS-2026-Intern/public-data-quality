from collections import Counter
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.application.services.categorical_validation.column_validation import (
    is_candidate_column,
    llm_skip_reason,
    validation_values,
)
from backend.config.categorical import CATEGORICAL_LLM_MAX_VALUES
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


def test_categorical_llm_candidate_allows_more_than_thirty_distinct_values() -> None:
    column = _categorical_column(distinct_count=45)
    counter = Counter({f"값{index}": index + 1 for index in range(45)})

    assert is_candidate_column(column) is True
    assert llm_skip_reason(column, counter) is None


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
