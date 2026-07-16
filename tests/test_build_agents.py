from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import backend.infrastructure.orchestration.agents as agents_module
from backend.application.dto import PipelineExecutionRequest
from backend.config.llm import LLM_FAST_MODEL, LLM_STRONG_MODEL


def test_build_agents_skips_llm_client_construction_when_disabled(monkeypatch) -> None:
    client_calls = {"count": 0}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            client_calls["count"] += 1

    monkeypatch.setattr(agents_module, "ChatLLMClient", FakeClient)

    agents = agents_module.build_agents(PipelineExecutionRequest(use_llm_agents=False))

    assert client_calls["count"] == 0
    assert agents.rule_router.column_resolver is None
    assert agents.semantic_profiler.semantic_profiler is None
    assert agents.categorical_semantic_validator.validator is None
    assert agents.final_finding_verifier.verifier is None


def test_build_agents_uses_bizrouter_default_models_when_request_models_are_missing(monkeypatch) -> None:
    model_names: list[str] = []

    class FakeClient:
        def __init__(self, *args, **kwargs):
            model_names.append(kwargs.get("model_name", ""))
            self.model_name = kwargs.get("model_name", "")
            self.enabled = True
            self.last_error = ""
            self.last_response_preview = ""

    monkeypatch.delenv("BIZROUTER_FAST_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_FAST_MODEL", raising=False)
    monkeypatch.delenv("BIZROUTER_STRONG_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_STRONG_MODEL", raising=False)
    monkeypatch.delenv("BIZROUTER_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.setattr(agents_module, "ensure_runtime_environment", lambda: None)
    monkeypatch.setattr(agents_module, "ChatLLMClient", FakeClient)

    agents_module.build_agents(PipelineExecutionRequest(use_llm_agents=True, openai_api_key="sk-br-v1-test"))

    assert model_names == [LLM_FAST_MODEL, LLM_STRONG_MODEL]


def test_build_agents_applies_single_request_model_to_fast_and_strong(monkeypatch) -> None:
    model_names: list[str] = []

    class FakeClient:
        def __init__(self, *args, **kwargs):
            model_names.append(kwargs.get("model_name", ""))
            self.model_name = kwargs.get("model_name", "")
            self.enabled = True
            self.last_error = ""
            self.last_response_preview = ""

    monkeypatch.setattr(agents_module, "ensure_runtime_environment", lambda: None)
    monkeypatch.setattr(agents_module, "ChatLLMClient", FakeClient)

    agents_module.build_agents(
        PipelineExecutionRequest(
            use_llm_agents=True,
            openai_api_key="sk-br-v1-test",
            llm_model="openai/gpt-5-nano",
        )
    )

    assert model_names == ["openai/gpt-5-nano", "openai/gpt-5-nano"]
