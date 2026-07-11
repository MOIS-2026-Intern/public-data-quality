from __future__ import annotations

from collections import Counter
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.application.agents.routing import LLMRoutingAgent
from backend.application.services.categorical_validation.llm_findings import apply_llm_categorical_findings
from backend.application.services.categorical_validation.row_selection import context_columns
from backend.domain.policies.categorical import allows_local_prefix_truncation, apply_local_categorical_findings
from backend.domain.policies.categorical.text import looks_malformed_text_value
from backend.domain.entities.models import ColumnProfile, DatasetMeta
from backend.domain.policies.columns.rules import validate_column


def _dataset_meta() -> DatasetMeta:
    return DatasetMeta(
        dataset_id="dataset",
        dataset_name="테스트",
        provider_name="기관",
        data_format="csv",
    )


def _column(name: str, *, samples: list[str] | None = None) -> ColumnProfile:
    values = samples or ["https://example.com/a", "https://example.com/b"]
    return ColumnProfile(
        raw_name=name,
        normalized_name=name,
        source="response",
        semantic_tags=[],
        assigned_rules=[],
        sample_values=values,
        top_values=[(values[0], 1)],
        inferred_primitive_type="string",
        distinct_count=2,
        non_empty_count=2,
    )


def test_free_text_columns_do_not_receive_rule_mapping() -> None:
    state = {
        "use_llm_agents": False,
        "columns": [
            _column("기타 사항", samples=["별도 문의", "해당 없음"]),
            _column("서비스url"),
            _column("사이트"),
            _column("대표문의", samples=["복지로 홈페이지 참조", "대표번호 및 사이트 참조"]),
        ],
    }

    result = LLMRoutingAgent().run(state)

    for column in result["columns"]:
        assert column.semantic_tags == ["free_text"]
        assert column.format_kind == "free_format"
        assert column.assigned_rules == []


def test_free_text_columns_do_not_emit_missing_rule_manual_review() -> None:
    column = _column("기타 사항", samples=["별도 문의", "해당 없음"])

    findings = validate_column(column, _dataset_meta(), [{"기타 사항": "별도 문의"}])

    assert findings == []


def test_free_text_columns_skip_local_prefix_truncation_detector() -> None:
    column = _column("서비스url", samples=["https://example.com/service"])

    assert allows_local_prefix_truncation(column) is False


def test_url_values_are_not_malformed_text() -> None:
    assert not looks_malformed_text_value(
        "https://www.bokjiro.go.kr/ssis-tbu/twataa/wlfareInfo/moveTWAT52011M.do?wlfareInfoId=WLF00005447&wlfareInfoReldBztpCd=01"
    )
    assert not looks_malformed_text_value("근로복지공단https://www.comwel.or.kr")
    assert not looks_malformed_text_value(
        "NH농협http://banking.nonghyup.com SH수협http://suhyup-bank.com 산림조합http://nfcf.or.kr"
    )


def test_free_text_url_columns_skip_local_malformed_findings() -> None:
    value = (
        "https://www.bokjiro.go.kr/ssis-tbu/twataa/wlfareInfo/moveTWAT52011M.do"
        "?wlfareInfoId=WLF00005447&wlfareInfoReldBztpCd=01"
    )
    column = _column("서비스URL", samples=[value])
    findings = []

    counts = apply_local_categorical_findings(
        column=column,
        rows=[{"서비스URL": value}],
        counter=Counter({value: 1}),
        findings=findings,
    )

    assert counts.malformed_count == 0
    assert findings == []


def test_free_format_columns_skip_all_local_detectors() -> None:
    column = _column("기타 사항", samples=["초등", "초등학교", "불법주정차빈??"])
    rows = [
        {"기타 사항": "초등"},
        {"기타 사항": "초등학교"},
        {"기타 사항": "불법주정차빈??"},
    ]
    findings = []

    counts = apply_local_categorical_findings(
        column=column,
        rows=rows,
        counter=Counter(row["기타 사항"] for row in rows),
        findings=findings,
    )

    assert not counts.has_findings
    assert findings == []


def test_free_format_llm_findings_keep_only_out_of_domain_values() -> None:
    column = _column("기타 사항", samples=["별도 문의", "복지 서비스 안내"])
    column.semantic_tags = ["free_text"]
    column.format_kind = "free_format"
    rows = [
        {"기타 사항": "복지 서비스 안내"},
        {"기타 사항": "2026-99-99"},
        {"기타 사항": "처리완료"},
    ]
    result = {
        "domain_label": "복지 서비스 관련 기타 설명",
        "normalizations": [
            {
                "source": "복지 서비스 안내",
                "target": "복지서비스 안내",
                "reason": "띄어쓰기 표준화가 가능합니다.",
                "confidence": 0.95,
            }
        ],
        "invalid_format_values": [
            {
                "value": "2026-99-99",
                "issue_type": "date_invalid",
                "reason": "날짜 형식처럼 보입니다.",
                "confidence": 0.95,
            }
        ],
        "out_of_domain_values": [
            {
                "value": "처리완료",
                "reason": "기타 사항 컬럼 도메인과 무관한 상태값입니다",
                "confidence": 0.95,
            }
        ],
        "needs_manual_review": [
            {
                "value": "2026-99-99",
                "reason": "도메인 관련성이 애매합니다.",
                "confidence": 0.70,
            }
        ],
        "_llm_model": "test",
        "_llm_stage": "strong",
        "_llm_escalated": True,
    }
    findings = []

    generated = apply_llm_categorical_findings(
        column=column,
        rows=rows,
        result=result,
        findings=findings,
    )

    assert generated == 1
    assert len(findings) == 1
    assert findings[0].rule_id == "categorical_value_out_of_domain"
    assert findings[0].row_indexes == [3]


def test_free_format_columns_are_excluded_from_row_context_validation() -> None:
    free_column = _column("기타 사항", samples=["센터 안내"])
    free_column.semantic_tags = ["free_text"]
    free_column.format_kind = "free_format"
    fixed_column = _column("시설명", samples=["행복센터"])
    fixed_column.semantic_tags = ["name"]
    fixed_column.format_kind = "fixed_format"

    selected = context_columns([free_column, fixed_column])

    assert [column["raw_name"] for column in selected] == ["시설명"]


def test_structured_long_address_is_not_classified_as_free_text() -> None:
    column = _column(
        "주소",
        samples=[
            "서울특별시 중구 세종대로 110",
            "부산광역시 해운대구 센텀중앙로 97",
        ],
    )

    result = LLMRoutingAgent().run({"use_llm_agents": False, "columns": [column]})

    assert "address" in result["columns"][0].semantic_tags
    assert result["columns"][0].format_kind == "fixed_format"
    assert result["columns"][0].assigned_rules
