# VAI — AI VTuber Pipeline

## Architecture (ปัจจุบัน)
Input (CLI/GUI/Voice/Restream) → LLM → TTS → RVC → VB-Audio → OBS

## Infrastructure
- เครื่อง VAI: รัน app, TTS, RVC, Audio
- เครื่อง LLM: รัน LM Studio (main LLM) + Gemini fallback
- Network: WiFi เดียวกัน, ตั้ง LM_STUDIO_BASE_URL เป็น IP เครื่อง LLM

## Project Structure
VAI/
├── server/              # FastAPI backend (NEW)
│   ├── main.py          # uvicorn entry, CORS, lifespan
│   ├── state.py         # pipeline singleton + lock
│   └── routers/
│       ├── chat.py      # WebSocket /ws/chat
│       └── config.py    # REST /api/status, /api/backend, /api/history
├── frontend/            # Nuxt 4 frontend (NEW)
│   ├── pages/index.vue  # chat UI
│   ├── components/      # ChatBubble, BackendSwitcher
│   ├── composables/useVAISocket.ts
│   └── nuxt.config.ts
├── backends/            # LLM abstraction (M0)
│   ├── base.py, gemini.py, lmstudio.py, factory.py
├── core/                # Pipeline layer (M0)
│   ├── capability_registry.py
│   ├── prompt_builder.py
│   └── pipeline.py      # VTuberPipeline
├── main.py              # CLI entry (ยังคงไว้)
├── app.py               # tkinter GUI (legacy — ใช้ก่อน web พร้อม)
├── config/, tts/, rvc/, utils/  # ไม่เปลี่ยน
└── subtitle.txt         # OBS Text Source

## Run
- `Run.bat` — เปิด FastAPI :8000 + Nuxt :3000 พร้อมกัน
- Backend API docs: http://localhost:8000/docs
- WebSocket: ws://localhost:8000/ws/chat
## Key Decisions
- Backend: Gemini หรือ LM Studio สลับได้ใน runtime ด้วย `/backend`
- Subtitle: เขียนลง subtitle.txt → OBS Text Source
- RVC fallback: copy TTS output ถ้า Applio ไม่พร้อม
- Expression: keyword matching ภาษาไทย (ยังหยาบอยู่ รอ refactor)
- LLM response: return JSON `{"action":"skip/respond","text":"...","expression":"...","motion":"..."}`
- Classify SKIP/RESPOND: รวมใน 1 LLM call เดียว ไม่แยก classifier
- Expression auto-clear: กลับ neutral หลัง 2 วินาที

## Expression Mapping (ปัจจุบัน)
- โกรธ, แย่ → angry
- ดี, ยิ้ม → smile_happy
- เศร้า, ทุกข์ → sad

## อย่าแตะ
- rvc/applio_stub.py — interface กับ Applio ซับซ้อน ระวัง
- LM_STUDIO_TIMEOUT ตั้งไว้ 10-15 วิ อย่าเพิ่ม

---

## Milestones

### ⚙️ M-1 — Infrastructure Setup ✅
- ย้าย LM Studio ไปรันบนเครื่อง LLM แยก (ผู้ใช้ทำ)
- ตั้ง LM_STUDIO_BASE_URL=http://<IP>:1234 ใน .env
- ✅ health check `backends/lmstudio.py::is_healthy()` ping /v1/models ก่อนทุก call
- ✅ auto-fallback → Gemini อัตโนมัติผ่าน `backends/factory.py::get_backend()`
- ✅ Startup แสดง LM Studio URL + connection status

### 🏗️ M0 — Architecture Refactor ✅
- ✅ `backends/` — abstract LLMBackend (base, gemini, lmstudio, factory)
- ✅ `core/capability_registry.py` — VAI รู้ว่าตัวเองทำ expression อะไรได้บ้าง
- ✅ `core/prompt_builder.py` — Dynamic System Prompt จาก Registry
- ✅ `core/pipeline.py` — VTuberPipeline รวม LLM→TTS→RVC→Audio→Subtitle
- ✅ `utils/subtitle.py` — subtitle/expression timer แยกออกจาก main
- ✅ `main.py` slim (entry point + backward-compat wrappers)
- ✅ `app.py` ใช้ VTuberPipeline แทน _process_message 50+ บรรทัด

### 🔨 M1 — Core Features
1. ลด latency — streaming TTS ระหว่าง LLM response
2. Expression + Motion — ให้ LLM return JSON ครบ
3. SKIP/RESPOND — รวมใน system prompt 1 call
4. Fallback อัตโนมัติ LM Studio → Gemini

### 🧠 M2 — Memory (ง่ายก่อน)
- เก็บ chat history เป็น JSON per user
- Person profile ง่ายๆ (ชื่อ, facts, last seen)
- LLM extract facts อัตโนมัติหลัง session

### 🤖 M3 — Discord Bot Integration
- VAI ตอบใน Discord channel ได้
- รู้จัก Discord user เชื่อมกับ person profile
- Share memory เดียวกับ Restream chat

### 🗄️ M4 — Memory ระยะยาว (เมื่อ community โต)
- ย้าย profile → SQLite
- ย้าย episode memory → ChromaDB (local)
- Semantic search "เคยคุยเรื่องอะไร"

### 🎤 M5 — Voice Recognition (optional)
- จำเสียงเจ้าของและกลุ่มเพื่อนได้
- Speaker diarization — รู้ว่าใครพูด
- เชื่อมกับ person profile อัตโนมัติ

### 🧬 M6 — Autonomous Behavior
**Phase 1 — Approval Mode**
- VAI มี scheduler "คิด" เป็นระยะ
- ทุก action ต้องแจ้งเจ้าของ approve ก่อน
- Log ทุก action ที่ VAI อยากทำ

**Phase 2 — Whitelist**
- action ที่ approve บ่อยๆ → ทำเองได้เลย
- Rate limit per action (Discord 1 ครั้ง/วัน/คน)
- Context check ก่อน action (owner online?, stream live?)

**Phase 3 — Full Autonomous**
- VAI ตัดสินใจเองได้ภายใน Guardrails
- Guardrails: rate limit, context check, action whitelist
- เมื่อมั่นใจใน behavior แล้วเท่านั้น

### 👁️ M7 — Vision (ในอนาคต)
- Screen capture ทุก 10-30 วิ
- ส่ง Gemini Vision วิเคราะห์
- AI คอมเมนต์เกม realtime

---

## Workflow (ทำตามนี้ทุกครั้ง อย่าข้ามขั้นตอน)

### ก่อนเริ่มทุกครั้ง
- อ่าน CLAUDE.md และ codebase ให้ครบก่อน
- ถามถ้าไม่ชัด อย่า assume
- วาง plan สั้นๆ ให้ approve ก่อนลงมือ

### Solution Design (ก่อนลงมือเขียนโค้ดทุกครั้ง)

Present ในรูปแบบนี้เสมอ:

**🎯 Goal:** [สรุป requirement 1 บรรทัด]

**Options:**
| | Option A | Option B | Option C |
|---|---|---|---|
| วิธี | ... | ... | ... |
| ความยาก | ง่าย | กลาง | ยาก |
| ต่อยอด | ได้/ไม่ได้ | ได้/ไม่ได้ | ได้/ไม่ได้ |
| เหมาะ Milestone | M1 | M2 | M3 |

**✅ แนะนำ:** Option X เพราะ [เหตุผล 1 บรรทัด]
**⚠️ Trade-off:** [สิ่งที่เสียไป]

→ รอ approve ก่อนลงมือทุกครั้ง

### Implementation Loop
1. เขียน test ก่อน (ยังไม่มีโค้ด)
2. Implement จนผ่าน test
3. Refactor ถ้าจำเป็น — test ต้องยังผ่านอยู่

### ก่อน Integrate
- รัน existing test suite ทั้งหมด
- ถ้ามี regression → แก้ก่อน ห้าม integrate

### หลัง Integrate
- รัน integration test
- ถ้าไม่ผ่าน → แก้และวนซ้ำ
- ถ้าผ่าน → สรุปสิ่งที่เปลี่ยนแปลงให้ชัดเจน
- บันทึกเหตุผลที่เลือก solution นี้ใน comment หรือ CLAUDE.md

### กฎเหล็ก
- ห้าม integrate โค้ดที่ test ไม่ผ่าน
- ถ้าแก้แล้วยังไม่ผ่าน 2 รอบ → หยุดแล้วรายงานปัญหาให้ชัด
- ห้ามแก้หลายอย่างพร้อมกัน ทำทีละ feature
- ห้ามเลือก solution ที่ block milestone ถัดไป