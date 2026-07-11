from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import backend.infrastructure.orchestration.agents as agents_module


def test_build_agents_skips_llm_client_construction_when_disabled(monkeypatch) -> None:
    client_calls = {"count": 0}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            client_calls["count"] += 1

    monkeypatch.setattr(agents_module, "ChatLLMClient", FakeClient)

    agents = agents_module.build_agents(use_llm_agents=False)

    assert client_calls["count"] == 0
    assert agents["rule_router"].column_resolver is None
    assert agents["semantic_profiler"].semantic_profiler is None
    assert agents["categorical_semantic_validator"].validator is None
    assert agents["final_finding_verifier"].verifier is None
