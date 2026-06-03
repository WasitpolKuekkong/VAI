from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResponse:
    text: str
    expression: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0


class LLMBackend(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def chat(self, messages: list[dict[str, str]]) -> LLMResponse: ...

    @abstractmethod
    def is_healthy(self) -> bool: ...
