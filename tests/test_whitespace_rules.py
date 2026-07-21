from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.domain.entities.models import ColumnProfile, DatasetMeta
from backend.domain.policies.columns.rules import validate_column


def _dataset_meta() -> DatasetMeta:
    return DatasetMeta(dataset_id="dataset", dataset_name="dataset")


def _text_column(*, values: list[str]) -> ColumnProfile:
    non_empty_values = [value for value in values if value]
    distinct_values = list(dict.fromkeys(non_empty_values))
    return ColumnProfile(
        raw_name="가격정보",
        normalized_name="가격정보",
        source="response",
        semantic_tags=["name"],
        assigned_rules=["required_value"],
        inferred_primitive_type="text",
        non_empty_count=len(non_empty_values),
        null_count=len(values) - len(non_empty_values),
        null_ratio=round((len(values) - len(non_empty_values)) / len(values), 4) if values else None,
        distinct_count=len(distinct_values),
        sample_values=distinct_values[:5],
        top_values=[(value, 1) for value in distinct_values[:5]],
    )


def test_whitespace_rule_sends_minor_cases_to_manual_review() -> None:
    values = [
        " 15000",
        "가격  정보",
        "15000 ~ 20000",
    ]
    rows = [{"가격정보": value} for value in values]

    findings = validate_column(_text_column(values=values), _dataset_meta(), rows)

    assert len(findings) == 2
    assert findings[0].rule_id == "whitespace_manual_review"
    assert findings[0].finding_type == "manual_review"
    assert findings[0].severity == "info"
    assert findings[0].row_indexes == [1]
    assert findings[0].message == "문자열 맨 앞에 공백이 의심됩니다."
    assert findings[1].rule_id == "whitespace_manual_review"
    assert findings[1].row_indexes == [2]
    assert findings[1].message == "'가격'과 '정보' 사이에 공백 이상이 의심됩니다."


def test_whitespace_rule_keeps_only_strong_cases_as_issue() -> None:
    values = [
        " 15000",
        "15000 ~  20000",
        "가격   정보",
    ]
    rows = [{"가격정보": value} for value in values]

    findings = validate_column(_text_column(values=values), _dataset_meta(), rows)

    assert len(findings) == 2
    assert findings[0].rule_id == "whitespace_issue"
    assert findings[0].finding_type == "issue"
    assert findings[0].row_indexes == [2, 3]
    assert findings[1].rule_id == "whitespace_manual_review"
    assert findings[1].finding_type == "manual_review"
    assert findings[1].row_indexes == [1]
    assert findings[1].message == "문자열 맨 앞에 공백이 의심됩니다."


def test_whitespace_rule_describes_column_name_issue() -> None:
    column = _text_column(values=["정상값"])
    column = column.model_copy(update={"raw_name": " 가격정보"})

    findings = validate_column(column, _dataset_meta(), [{" 가격정보": "정상값"}])

    assert len(findings) == 1
    assert findings[0].rule_id == "whitespace_manual_review"
    assert findings[0].message == "컬럼명에서 문자열 맨 앞에 공백이 의심됩니다."


def test_whitespace_rule_describes_multiple_minor_gaps() -> None:
    rows = [{"가격정보": "A  B  C"}]

    findings = validate_column(_text_column(values=["A  B  C"]), _dataset_meta(), rows)

    assert len(findings) == 1
    assert findings[0].rule_id == "whitespace_manual_review"
    assert findings[0].message == (
        "'A'과 'B' 사이에 공백 이상이 의심됩니다. "
        "'B'과 'C' 사이에 공백 이상이 의심됩니다."
    )


def test_terminal_question_mark_fragment_is_special_character_issue_for_structured_column() -> None:
    value = "박수홍Bakery&caf?"
    column = ColumnProfile(
        raw_name="업소명",
        normalized_name="업소명",
        source="response",
        semantic_tags=["name"],
        assigned_rules=["required_value", "garbled_text", "whitespace_special_characters"],
        inferred_primitive_type="text",
        non_empty_count=1,
        distinct_count=1,
        sample_values=[value],
        top_values=[(value, 1)],
    )

    findings = validate_column(column, _dataset_meta(), [{"업소명": value}])

    assert len(findings) == 1
    assert findings[0].rule_id == "special_character_issue"
    assert findings[0].finding_type == "issue"
    assert findings[0].row_indexes == [1]
    assert findings[0].evidence == [value]


def test_korean_business_name_terminal_punctuation_is_allowed() -> None:
    values = ["까까 보까!", "머리해요!", "네일어때?"]
    column = ColumnProfile(
        raw_name="업소명",
        normalized_name="업소명",
        source="response",
        semantic_tags=["name"],
        assigned_rules=["required_value", "garbled_text", "whitespace_special_characters"],
        inferred_primitive_type="text",
        non_empty_count=len(values),
        distinct_count=len(values),
        sample_values=values,
        top_values=[(value, 1) for value in values],
    )

    findings = validate_column(column, _dataset_meta(), [{"업소명": value} for value in values])

    assert findings == []


def test_parenthetical_korean_initials_in_business_name_are_allowed() -> None:
    value = "막창집(ㅁㅊ집)"
    column = ColumnProfile(
        raw_name="업소명",
        normalized_name="업소명",
        source="response",
        semantic_tags=["name"],
        assigned_rules=["required_value", "garbled_text", "whitespace_special_characters"],
        inferred_primitive_type="text",
        non_empty_count=1,
        distinct_count=1,
        sample_values=[value],
        top_values=[(value, 1)],
    )

    findings = validate_column(column, _dataset_meta(), [{"업소명": value}])

    assert findings == []


def test_terminal_question_mark_is_allowed_for_free_text_column() -> None:
    value = "운영 여부를 확인해야 하나요?"
    column = ColumnProfile(
        raw_name="내용",
        normalized_name="내용",
        source="response",
        semantic_tags=["free_text"],
        format_kind="free_format",
        assigned_rules=[],
        inferred_primitive_type="string",
        non_empty_count=1,
        distinct_count=1,
        sample_values=[value],
        top_values=[(value, 1)],
    )

    findings = validate_column(column, _dataset_meta(), [{"내용": value}])

    assert findings == []
