from __future__ import annotations

from core.capability_registry import CapabilityRegistry

_JSON_INSTRUCTION = """\

## รูปแบบการตอบ (บังคับเสมอ)
ตอบเป็น JSON บรรทัดเดียว ห้ามมี text นอก JSON เด็ดขาด

ถ้าจะตอบ:
{"action":"respond","text":"<บทพูด>","expression":"<expression>","motion":""}

ถ้าจะข้าม:
{"action":"skip"}

## กฎ SKIP / RESPOND
- ตอบเสมอ: [EiX2] พูดทุกกรณี
- ตอบเสมอ: ข้อความที่มี [TAGGED] นำหน้า (มีคน mention โดยตรง)
- ตอบ: มีคนพูดถึง VAI / มิโคล่า โดยตรง หรือถามคำถามชัดเจน
- ข้าม: viewer คุยกันเอง ไม่ได้ถาม VAI, คำทักทายทั่วไปที่ไม่ได้ถาม"""


def build_system_prompt(personality: str, registry: CapabilityRegistry) -> str:
    expressions = ", ".join(registry.expression_names()) if registry.expressions else "neutral"
    instruction = _JSON_INSTRUCTION + f"\n\n## Expression ที่ใช้ได้\n{expressions}"
    return personality + instruction
