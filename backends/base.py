from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResponse:
    text: str
    action: str = "respond"       # "respond" | "skip"
    expression: str | None = None
    motion: str = ""
    input_tokens: int = 0
    output_tokens: int = 0


def parse_llm_json(raw: str) -> LLMResponse:
    """
    Parse LLM output into LLMResponse.

    4-tier fallback:
      1. Strip <think> blocks and markdown fences, then json.loads()
      2. Regex-extract first {...} containing "action"
      3. Plain-text fallback → action=respond, text=raw
    """
    # Strip <think>...</think> (Qwen3 thinking mode leaking through)
    cleaned = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip()

    # Strip markdown code fences
    cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r'\s*```\s*$', '', cleaned, flags=re.MULTILINE).strip()

    # Tier 1 — direct parse
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict) and "action" in data:
            return _to_response(data)
    except (json.JSONDecodeError, ValueError):
        pass

    # Tier 2 — find embedded JSON object
    match = re.search(r'\{[^{}]*"action"[^{}]*\}', cleaned, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            return _to_response(data)
        except (json.JSONDecodeError, ValueError):
            pass

    # Tier 3 — plain text fallback → treat as respond
    return LLMResponse(text=cleaned or raw.strip())


def _to_response(data: dict) -> LLMResponse:
    action = str(data.get("action", "respond")).lower()
    if action not in ("respond", "skip"):
        action = "respond"
    return LLMResponse(
        text=str(data.get("text", "")).strip() if action == "respond" else "",
        action=action,
        expression=data.get("expression") or None,
        motion=str(data.get("motion", "") or ""),
    )


class LLMBackend(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def chat(self, messages: list[dict[str, str]]) -> LLMResponse: ...

    @abstractmethod
    def is_healthy(self) -> bool: ...
