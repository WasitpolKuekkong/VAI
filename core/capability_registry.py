from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ExpressionCapability:
    name: str
    description: str


@dataclass
class CapabilityRegistry:
    expressions: list[ExpressionCapability] = field(default_factory=list)

    @classmethod
    def default(cls) -> "CapabilityRegistry":
        return cls(
            expressions=[
                ExpressionCapability("smile_happy", "ยิ้มแย้ม มีความสุข ดีใจ"),
                ExpressionCapability("angry", "โกรธ หงุดหงิด ไม่พอใจ"),
                ExpressionCapability("sad", "เศร้า ผิดหวัง เสียใจ"),
            ]
        )

    def expression_names(self) -> list[str]:
        return [e.name for e in self.expressions]

    def add_expression(self, name: str, description: str = "") -> None:
        self.expressions.append(ExpressionCapability(name=name, description=description))
