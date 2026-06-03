from __future__ import annotations

import time

from google import genai

from backends.base import LLMBackend, LLMResponse
from utils.logger import logger

_ANGRY = ["โกรธ", "แย่", "ไม่ดี", "หัวเสีย", "ตรวจสอบ", "ปัญหา"]
_HAPPY = ["ดี", "ยิ้ม", "มีความสุข", "เยี่ยม", "ยอ", "ดีใจ"]
_SAD = ["เศร้า", "ทุกข์", "เสียใจ", "ผิดหวัง", "น่าเสียดาย"]


def _sentiment(text: str) -> str | None:
    t = text.lower()
    a = sum(1 for w in _ANGRY if w in t)
    h = sum(1 for w in _HAPPY if w in t)
    s = sum(1 for w in _SAD if w in t)
    if a and a >= h and a >= s:
        return "angry"
    if s and s >= h:
        return "sad"
    if h:
        return "smile_happy"
    return None


class GeminiBackend(LLMBackend):
    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model or "gemini-2.5-flash"
        self._client = genai.Client(api_key=api_key) if api_key else None

    @property
    def name(self) -> str:
        return "gemini"

    def is_healthy(self) -> bool:
        return bool(self._api_key)

    def chat(self, messages: list[dict[str, str]]) -> LLMResponse:
        if not self._api_key or self._client is None:
            raise RuntimeError("GOOGLE_AISTUDIO_API_KEY is not set")

        client = self._client
        parts: list[str] = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "").strip()
            if not content:
                continue
            if role == "system":
                parts.append(f"[System: {content}]")
            elif role == "user":
                parts.append(content)
            else:
                parts.append(f"{role.title()}: {content}")

        prompt = "\n".join(parts) if parts else "สวัสดี"
        delay = 10

        for attempt in range(1, 5):
            try:
                response = client.models.generate_content(model=self._model, contents=prompt)
                text = (response.text or "").strip()
                usage = response.usage_metadata
                input_tok = getattr(usage, "prompt_token_count", 0) or 0
                output_tok = getattr(usage, "candidates_token_count", 0) or 0
                return LLMResponse(
                    text=text,
                    expression=_sentiment(text),
                    input_tokens=input_tok,
                    output_tokens=output_tok,
                )
            except Exception as exc:
                s = str(exc)
                is_rate = "429" in s or "RESOURCE_EXHAUSTED" in s
                is_busy = "503" in s or "UNAVAILABLE" in s
                if (is_rate or is_busy) and attempt < 4:
                    label = "rate-limited (429)" if is_rate else "busy (503)"
                    logger.warning(f"🔄 Gemini {label}, retrying in {delay}s... ({attempt}/4)")
                    time.sleep(delay)
                    delay *= 2
                    continue
                raise

        return LLMResponse(text="")
