from __future__ import annotations

import hashlib
import json
import os
import threading
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from backend.config.llm import (
    LLM_CACHE_MAX_ENTRIES,
    LLM_DEFAULT_MODEL,
    LLM_REQUEST_TIMEOUT_SECONDS,
    OPENAI_DEFAULT_API_URL,
)


def _first_env(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


@dataclass
class ChatLLMResponse:
    content: str


class ChatLLMClient:
    _cache: OrderedDict[str, str] = OrderedDict()
    _cache_lock = threading.Lock()

    def __init__(
        self,
        model_name: str | None = None,
        api_url: str | None = None,
        api_key: str | None = None,
        timeout_seconds: int = LLM_REQUEST_TIMEOUT_SECONDS,
    ):
        self.model_name = model_name or _first_env("BIZROUTER_MODEL", "OPENAI_MODEL") or LLM_DEFAULT_MODEL
        self.api_url = self._normalize_api_url(
            api_url or _first_env("BIZROUTER_API_URL", "OPENAI_API_URL") or OPENAI_DEFAULT_API_URL
        )
        self.api_key = api_key or _first_env("BIZROUTER_API_KEY", "OPENAI_API_KEY") or ""
        self.timeout_seconds = timeout_seconds
        self.last_error = ""
        self.last_response_preview = ""

    def _normalize_api_url(self, value: str | None) -> str:
        normalized = (value or "").strip()
        return normalized or OPENAI_DEFAULT_API_URL

    def _configuration_error(self) -> str:
        if not self.model_name:
            return "LLM_MODEL missing"
        if not self.api_url:
            return "LLM_API_URL missing"
        if not self.api_key:
            return "LLM_API_KEY missing"
        try:
            self.api_url.encode("latin-1")
        except UnicodeEncodeError:
            return "LLM_API_URL contains unsupported URL characters"
        try:
            f"Bearer {self.api_key}".encode("latin-1")
        except UnicodeEncodeError:
            return "LLM_API_KEY contains unsupported header characters"
        return ""

    @property
    def enabled(self) -> bool:
        return not bool(self._configuration_error())

    def _messages(self, prompt: str, *, system_prompt: str | None = None) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages

    def _invoke(self, prompt: str, *, system_prompt: str | None = None, json_response: bool = False) -> ChatLLMResponse | None:
        configuration_error = self._configuration_error()
        if configuration_error:
            self.last_error = configuration_error
            self.last_response_preview = ""
            return None
        return self._post_chat(self._build_payload(self._messages(prompt, system_prompt=system_prompt), json_response=json_response))

    def invoke(self, prompt: str, *, system_prompt: str | None = None) -> ChatLLMResponse | None:
        return self._invoke(prompt, system_prompt=system_prompt)

    def _build_payload(self, messages: list[dict[str, str]], *, json_response: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
        }
        if json_response:
            payload["response_format"] = {"type": "json_object"}
        return payload

    @classmethod
    def clear_cache(cls) -> None:
        with cls._cache_lock:
            cls._cache.clear()

    @staticmethod
    def _cache_enabled() -> bool:
        value = os.getenv("LLM_CACHE_ENABLED", "1").strip().lower()
        return value not in {"0", "false", "no", "off"}

    def _cache_key(self, payload: dict[str, Any]) -> str:
        raw = json.dumps(
            {"api_url": self.api_url, "payload": payload},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @classmethod
    def _get_cached_content(cls, key: str) -> str | None:
        with cls._cache_lock:
            content = cls._cache.get(key)
            if content is None:
                return None
            cls._cache.move_to_end(key)
            return content

    @classmethod
    def _set_cached_content(cls, key: str, content: str) -> None:
        if LLM_CACHE_MAX_ENTRIES <= 0:
            return
        with cls._cache_lock:
            cls._cache[key] = content
            cls._cache.move_to_end(key)
            while len(cls._cache) > LLM_CACHE_MAX_ENTRIES:
                cls._cache.popitem(last=False)

    def _post_chat(self, payload: dict[str, Any]) -> ChatLLMResponse | None:
        if not self.enabled:
            return None
        cache_key = self._cache_key(payload)
        if self._cache_enabled():
            cached_content = self._get_cached_content(cache_key)
            if cached_content is not None:
                self.last_response_preview = cached_content[:300]
                self.last_error = ""
                return ChatLLMResponse(content=cached_content)

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        data = json.dumps(payload).encode("utf-8")
        request = Request(
            self.api_url,
            data=data,
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            try:
                error_body = exc.read().decode("utf-8")
            except Exception:
                error_body = ""
            self.last_error = f"HTTP {exc.code}: {error_body or exc.reason}"
            return None
        except URLError as exc:
            self.last_error = f"URL error: {exc.reason}"
            return None
        except TimeoutError:
            self.last_error = "request timeout"
            return None
        except UnicodeEncodeError:
            self.last_error = "HTTP header encoding error: API key contains unsupported characters"
            return None
        except json.JSONDecodeError:
            self.last_error = "invalid JSON response"
            return None

        content = self._extract_content(body)
        if not content:
            error = body.get("error")
            self.last_error = f"LLM API error: {self._extract_error(error)}" if error else "empty response content"
            self.last_response_preview = ""
            return None
        self.last_response_preview = content[:300]
        self.last_error = ""
        if self._cache_enabled():
            self._set_cached_content(cache_key, content)
        return ChatLLMResponse(content=content)

    def invoke_json(self, prompt: str, *, system_prompt: str | None = None) -> ChatLLMResponse | None:
        return self._invoke(prompt, system_prompt=system_prompt, json_response=True)

    @staticmethod
    def _extract_content(body: dict[str, Any]) -> str:
        choices = body.get("choices")
        if isinstance(choices, list) and choices:
            first_choice = choices[0]
            if isinstance(first_choice, dict):
                message = first_choice.get("message")
                if isinstance(message, dict):
                    content = message.get("content", "")
                    if isinstance(content, str):
                        return content
        return ""

    @staticmethod
    def _extract_error(error: Any) -> str:
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str) and message:
                return message
            return json.dumps(error, ensure_ascii=False)
        if isinstance(error, str):
            return error
        return str(error)
