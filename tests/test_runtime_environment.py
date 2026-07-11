from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import backend.infrastructure.orchestration.agents as agents_module


def test_build_agents_loads_runtime_environment_only_when_llm_is_enabled(monkeypatch) -> None:
    env_calls = {"count": 0}
    client_calls = {"count": 0}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            client_calls["count"] += 1
            self.model_name = kwargs.get("model_name", "fake-model")
            self.enabled = True
            self.last_error = ""
            self.last_response_preview = ""

    def fake_ensure_runtime_environment() -> None:
        env_calls["count"] += 1

    monkeypatch.setattr(agents_module, "ensure_runtime_environment", fake_ensure_runtime_environment)
    monkeypatch.setattr(agents_module, "ChatLLMClient", FakeClient)

    agents_module.build_agents(use_llm_agents=False)
    agents_module.build_agents(use_llm_agents=True)

    assert env_calls["count"] == 1
    assert client_calls["count"] == 2
