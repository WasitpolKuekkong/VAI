from __future__ import annotations

from core.capability_registry import CapabilityRegistry


def build_system_prompt(personality: str, registry: CapabilityRegistry) -> str:
    """Append VAI's available expressions to the personality prompt."""
    if not registry.expressions:
        return personality
    names = ", ".join(registry.expression_names())
    return personality + f"\n\nExpression ที่ใช้ได้: {names}"
