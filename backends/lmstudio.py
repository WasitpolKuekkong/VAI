from __future__ import annotations

import requests

from backends.base import LLMBackend, LLMResponse


class LMStudioBackend(LLMBackend):
    def __init__(
        self,
        base_url: str,
        model: str,
        temperature: float,
        max_tokens: int,
        timeout: int,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._timeout = timeout

    @property
    def name(self) -> str:
        return "lmstudio"

    def is_healthy(self, ping_timeout: float = 3.0) -> bool:
        try:
            resp = requests.get(f"{self._base_url}/v1/models", timeout=ping_timeout)
            return resp.status_code == 200
        except Exception:
            return False

    def chat(self, messages: list[dict[str, str]]) -> LLMResponse:
        url = f"{self._base_url}/v1/chat/completions"
        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
            "stream": False,
        }
        response = requests.post(url, json=payload, timeout=self._timeout)
        response.raise_for_status()
        text = response.json()["choices"][0]["message"]["content"].strip()
        return LLMResponse(text=text)
