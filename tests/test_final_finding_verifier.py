from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.application.agents.final_verifier import FinalFindingVerificationAgent
from backend.application.prompts.verification import final_finding_verification_prompt
from backend.application.services.verification.final_finding_verifier import (
    _apply_final_verification,
    _finding_candidates,
)
from backend.domain.entities.models import DatasetMeta
from backend.domain.policies.helpers import build_finding


class FakeVerifier:
    enabled = True
    last_error = ""
    last_response_preview = ""
    last_model_name = "fake-strong"

    def verify(self, *, dataset_name, provider_name, candidates):
        assert dataset_name == "테스트"
        assert provider_name == "기관"
        return {
            "verified_findings": [
                {
                    "id": "f0",
                    "keep": True,
                    "reason": "날짜 컬럼 값이 실제 날짜 형식으로 해석되지 않습니다.",
                    "confidence": 0.96,
                    "message": "날짜 형식 오류입니다.",
                },
                {
                    "id": "f1",
                    "keep": False,
                    "reason": "사이트 값은 자유 입력 URL/설명으로 볼 수 있어 오류 근거가 부족합니다.",
                    "confidence": 0.40,
                    "message": "",
                },
            ]
        }


class SuppressingVerifier:
    enabled = True
    last_error = ""
    last_response_preview = ""
    last_model_name = "fake-strong"

    def verify(self, *, dataset_name, provider_name, candidates):
        return {
            "verified_findings": [
                {
                    "id": candidate["id"],
                    "keep": False,
                    "reason": "근거가 부족합니다.",
                    "confidence": 0.40,
                    "message": "",
                }
                for candidate in candidates
            ]
        }


def test_final_finding_verifier_keeps_only_llm_confirmed_issues() -> None:
    findings = [
        build_finding(
            column_name="기준일자",
            severity="warning",
            category_group="domain_validity",
            criterion_name="date_domain",
            message="날짜 형식이 올바르지 않습니다.",
            row_indexes=[1],
            evidence=["detector:test"],
        ),
        build_finding(
            column_name="사이트",
            severity="warning",
            category_group="domain_validity",
            criterion_name="categorical_semantic_domain",
            rule_id="categorical_value_truncated",
            message="값이 짧아 잘림이 의심됩니다.",
            row_indexes=[2],
            evidence=["detector:prefix_truncation"],
        ),
    ]
    agent = FinalFindingVerificationAgent(verifier=FakeVerifier())

    result = agent.run(
        {
            "use_llm_agents": True,
            "dataset_meta": DatasetMeta(dataset_id="d", dataset_name="테스트", provider_name="기관"),
            "validation_rows": [
                {"기준일자": "2026-99-99"},
                {"사이트": "복지로"},
            ],
            "findings": findings,
            "agent_traces": [],
        }
    )

    assert len(result["findings"]) == 1
    assert result["findings"][0].column_name == "기준일자"
    assert result["findings"][0].message == "날짜 형식이 올바르지 않습니다."
    assert result["findings"][0].llm_final_verification == "날짜 컬럼 값이 실제 날짜 형식으로 해석되지 않습니다."
    assert "final_verifier:llm" in result["findings"][0].evidence


def test_final_finding_verifier_preserves_institution_suffix_truncation() -> None:
    finding = build_finding(
        column_name="시설유형",
        severity="warning",
        category_group="domain_validity",
        criterion_name="categorical_semantic_domain",
        rule_id="categorical_value_truncated",
        message="'초등' 값은 '초등학교' 값의 앞부분과 일치해 입력 중 잘림 가능성이 있습니다.",
        row_indexes=[1],
        related_columns=["시설유형"],
        evidence=[
            "matched_full_value:초등학교",
            "truncated_count:1",
            "full_count:1",
            "mapping:one_to_one",
            "detector:prefix_truncation",
            "mapping:institution_suffix_completion",
        ],
    )
    agent = FinalFindingVerificationAgent(verifier=SuppressingVerifier())

    result = agent.run(
        {
            "use_llm_agents": True,
            "dataset_meta": DatasetMeta(dataset_id="d", dataset_name="테스트", provider_name="기관"),
            "validation_rows": [
                {"시설유형": "초등"},
                {"시설유형": "초등학교"},
            ],
            "findings": [finding],
            "agent_traces": [],
        }
    )

    assert len(result["findings"]) == 1
    assert result["findings"][0].rule_id == "categorical_value_truncated"
    assert "final_verifier:deterministic_institution_suffix" in result["findings"][0].evidence


def test_final_finding_verifier_does_not_append_english_reason_to_message() -> None:
    finding = build_finding(
        column_name="서비스명",
        severity="warning",
        category_group="completeness",
        criterion_name="whitespace_special_characters",
        rule_id="whitespace_issue",
        message="서비스명에 불필요한 공백이 포함되어 있습니다.",
        row_indexes=[1],
    )

    verified = _apply_final_verification(
        finding,
        {
            "keep": True,
            "reason": "The values contain trailing whitespace, which is likely not intended.",
            "confidence": 0.95,
            "message": "",
        },
        "fake-strong",
    )

    assert verified.message == "서비스명에 불필요한 공백이 포함되어 있습니다."
    assert verified.llm_final_verification == ""
    assert "The values" not in " ".join(verified.evidence)


def test_amount_domain_candidates_are_prioritized_for_llm_verification() -> None:
    date_finding = build_finding(
        column_name="기준일자",
        severity="warning",
        category_group="domain_validity",
        criterion_name="date_domain",
        message="날짜 형식이 올바르지 않습니다.",
        row_indexes=[1],
    )
    amount_finding = build_finding(
        column_name="가격1",
        severity="warning",
        category_group="domain_validity",
        criterion_name="amount_domain",
        message="금액 도메인 컬럼에 숫자 파싱이 되지 않는 값이 존재합니다.",
        row_indexes=[2],
    )

    candidates = _finding_candidates(
        [(0, date_finding), (1, amount_finding)],
        [{"기준일자": "2026-99-99"}, {"가격1": "9000(7000)"}],
    )

    assert [candidate["rule_id"] for candidate in candidates] == ["amount_domain", "date_domain"]
    assert candidates[0]["sample_rows"] == [{"row_index": 2, "values": {"가격1": "9000(7000)"}}]


def test_final_verification_prompt_treats_amount_parse_failures_semantically() -> None:
    prompt = final_finding_verification_prompt(
        dataset_name="테스트",
        provider_name="기관",
        candidates=[
            {
                "id": "f0",
                "column_name": "가격1",
                "rule_id": "amount_domain",
                "message": "금액 도메인 컬럼에 숫자 파싱이 되지 않는 값이 존재합니다.",
                "sample_rows": [{"row_index": 1, "values": {"가격1": "25,000~"}}],
            }
        ],
    )

    assert "amount_domain" in prompt
    assert "not a pure number" in prompt
    assert "parenthesized options" in prompt
    assert "deleted or unavailable status values" in prompt
