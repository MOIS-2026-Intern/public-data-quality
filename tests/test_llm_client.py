import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import backend.infrastructure.llm.client as client_module
from backend.config.llm import LLM_DEFAULT_MODEL, OPENAI_DEFAULT_API_URL
from backend.infrastructure.llm.client import ChatLLMClient


def test_chat_llm_client_uses_bizrouter_defaults_and_chat_completions_payload(monkeypatch) -> None:
    ChatLLMClient.clear_cache()
    captured: dict[str, object] = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self) -> bytes:
            return json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode("utf-8")

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["authorization"] = request.get_header("Authorization")
        captured["content_type"] = request.get_header("Content-type")
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(client_module, "urlopen", fake_urlopen)

    response = ChatLLMClient(api_key="sk-br-v1-test").invoke_json("hello", system_prompt="system")

    assert response is not None
    assert response.content == "ok"
    assert captured["url"] == OPENAI_DEFAULT_API_URL
    assert captured["method"] == "POST"
    assert captured["authorization"] == "Bearer sk-br-v1-test"
    assert captured["content_type"] == "application/json"
    assert captured["timeout"] == client_module.LLM_REQUEST_TIMEOUT_SECONDS
    assert captured["payload"] == {
        "model": LLM_DEFAULT_MODEL,
        "messages": [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "hello"},
        ],
        "response_format": {"type": "json_object"},
    }


def test_chat_llm_client_accepts_bizrouter_environment_variables(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_API_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("BIZROUTER_MODEL", "openai/gpt-5-mini")
    monkeypatch.setenv("BIZROUTER_API_URL", "https://api.bizrouter.ai/v1/chat/completions")
    monkeypatch.setenv("BIZROUTER_API_KEY", "sk-br-v1-env")

    client = ChatLLMClient()

    assert client.model_name == "openai/gpt-5-mini"
    assert client.api_url == "https://api.bizrouter.ai/v1/chat/completions"
    assert client.api_key == "sk-br-v1-env"
    assert client.enabled is True


def test_chat_llm_client_caches_successful_responses(monkeypatch) -> None:
    ChatLLMClient.clear_cache()
    call_count = 0

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self) -> bytes:
            return json.dumps({"choices": [{"message": {"content": "cached"}}]}).encode("utf-8")

    def fake_urlopen(request, timeout):
        nonlocal call_count
        call_count += 1
        return FakeResponse()

    monkeypatch.setattr(client_module, "urlopen", fake_urlopen)

    client = ChatLLMClient(api_key="sk-br-v1-test")
    first = client.invoke_json("same prompt", system_prompt="system")
    second = client.invoke_json("same prompt", system_prompt="system")

    assert first is not None
    assert second is not None
    assert first.content == "cached"
    assert second.content == "cached"
    assert call_count == 1
