from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResponse:
    text: str
    expression: str | None = None


class LLMBackend(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def chat(self, messages: list[dict[str, str]]) -> LLMResponse: ...

    @abstractmethod
    def is_healthy(self) -> bool: ...
