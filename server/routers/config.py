from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from backends.lmstudio import LMStudioBackend

router = APIRouter(prefix="/api")

try:
    import sounddevice as sd
    _SD_AVAILABLE = True
except Exception:
    _SD_AVAILABLE = False


class BackendSwitch(BaseModel):
    backend: str  # "gemini" | "lmstudio"


@router.get("/status")
async def get_status() -> dict:
    from server.state import pipeline
    if pipeline is None:
        return {"ready": False}

    cfg = pipeline.config
    lm = LMStudioBackend(
        base_url=cfg.lm_studio_base_url,
        model=cfg.model_name,
        temperature=cfg.temperature,
        max_tokens=cfg.max_tokens,
        timeout=cfg.request_timeout,
    )
    lm_healthy = await asyncio.to_thread(lm.is_healthy)
    return {
        "ready": True,
        "backend": cfg.preferred_backend,
        "lmstudio_url": cfg.lm_studio_base_url,
        "lmstudio_healthy": lm_healthy,
        "gemini_model": cfg.google_aistudio_model or "gemini-2.5-flash",
        "lmstudio_model": cfg.model_name,
        "history_count": len(pipeline.history),
        "speaker": pipeline.current_speaker,
        "pitch": pipeline.current_pitch,
    }


@router.post("/backend")
async def switch_backend(body: BackendSwitch) -> dict:
    from server.state import pipeline
    if pipeline is None:
        return {"ok": False, "error": "Server not ready"}
    backend = body.backend.lower()
    if backend not in ("gemini", "lmstudio"):
        return {"ok": False, "error": "Unknown backend"}
    pipeline.config.preferred_backend = backend
    return {"ok": True, "backend": backend}


@router.get("/audio-devices")
async def get_audio_devices() -> dict:
    if not _SD_AVAILABLE:
        return {"ok": False, "error": "sounddevice not installed", "devices": []}
    try:
        raw = await asyncio.to_thread(sd.query_devices)
        devices = []
        for i, d in enumerate(raw):  # type: ignore[arg-type]
            devices.append({
                "id": i,
                "name": d["name"],
                "max_input_channels": d["max_input_channels"],
                "max_output_channels": d["max_output_channels"],
            })
        return {"ok": True, "devices": devices}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "devices": []}


# ── Restream OAuth ────────────────────────────────────────────────────────────

@router.get("/restream/auth-url")
async def restream_auth_url() -> dict:
    from server.state import pipeline
    if pipeline is None:
        return {"ok": False, "error": "Server not ready"}
    cfg = pipeline.config
    if not cfg.restream_client_id:
        return {"ok": False, "error": "RESTREAM_CLIENT_ID not set in .env"}
    from utils.restream_client import build_auth_url
    url = build_auth_url(cfg.restream_client_id, cfg.restream_redirect_uri)
    return {"ok": True, "url": url}


@router.get("/restream/callback")
async def restream_callback(code: str, state: str | None = None) -> HTMLResponse:
    import server.state as state
    from utils.restream_client import exchange_code_sync, start_chat_listener

    if state.pipeline is None:
        return HTMLResponse("<p>❌ Server not ready</p>", status_code=503)

    cfg = state.pipeline.config
    try:
        token_data = await asyncio.to_thread(
            exchange_code_sync,
            code,
            cfg.restream_client_id,
            cfg.restream_client_secret,
            cfg.restream_redirect_uri,
        )
    except Exception as exc:
        return HTMLResponse(f"<p>❌ Token exchange failed: {exc}</p>", status_code=400)

    access_token = token_data.get("access_token")
    if not access_token:
        return HTMLResponse("<p>❌ No access token in response</p>", status_code=400)

    state.restream_access_token = access_token

    # Cancel previous listener if any
    if state.restream_task and not state.restream_task.done():
        state.restream_task.cancel()

    # Broadcast Restream chat messages to all active frontend WS connections
    async def _broadcast(msg: dict) -> None:
        # Always push to chat panel
        dead: set = set()
        for ws in list(state.active_ws):
            try:
                await ws.send_json({"type": "restream_chat", "message": msg})
            except Exception:
                dead.add(ws)
        state.active_ws -= dead

        # Forward to LLM if toggle is on
        if not state.restream_to_llm or state.pipeline is None:
            return
        text = (msg.get("text") or "").strip()
        if not text:
            return

        author = msg.get("author") or {}
        display_name = author.get("displayName", "")
        platform = author.get("type", "")
        owner_set = {
            n.strip().lower()
            for n in state.pipeline.config.restream_owner_names.split(",")
            if n.strip()
        }
        is_owner = display_name.lower() in owner_set

        # Priority: viewers skip when lock is busy OR owner tasks are pending
        if not is_owner:
            if state.processing_lock.locked() or state.pending_owner_tasks > 0:
                return

        prefix = f"[{platform.upper()} | {display_name}]: " if display_name else ""
        asyncio.create_task(_run_restream_turn(f"{prefix}{text}", is_owner))

    # Notify all open frontends that Restream is now connected
    for ws in list(state.active_ws):
        try:
            await ws.send_json({
                "type": "restream_status",
                "connected": True,
                "message": "Connected to Restream chat ✓",
            })
        except Exception:
            pass

    state.restream_task = asyncio.create_task(
        start_chat_listener(access_token, _broadcast)
    )

    return HTMLResponse("""<!DOCTYPE html>
<html>
<head>
<title>VAI — Restream</title>
<style>
  *{margin:0;padding:0;box-sizing:border-box}
  body{font-family:sans-serif;background:#18181b;color:#fff;
       display:flex;align-items:center;justify-content:center;height:100vh}
  .card{text-align:center;padding:2rem}
  .icon{font-size:3.5rem;margin-bottom:1rem}
  h2{margin-bottom:.5rem}
  p{color:#a1a1aa;font-size:.9rem}
</style>
</head>
<body>
<div class="card">
  <div class="icon">✅</div>
  <h2>Restream Connected!</h2>
  <p>กำลังรับ chat… คุณสามารถปิดหน้าต่างนี้ได้</p>
</div>
<script>setTimeout(() => window.close(), 2000)</script>
</body>
</html>""")


async def _ws_broadcast(data: dict[str, Any]) -> None:
    """Send JSON to every connected frontend WebSocket, pruning dead connections."""
    import server.state as _state
    dead: set = set()
    for ws in list(_state.active_ws):
        try:
            await ws.send_json(data)
        except Exception:
            dead.add(ws)
    _state.active_ws -= dead


async def _run_restream_turn(text: str, is_owner: bool) -> None:
    """Run one pipeline turn for a Restream message and broadcast results."""
    import server.state as _state
    from core.pipeline import TurnCallbacks

    if _state.pipeline is None:
        return

    if is_owner:
        _state.pending_owner_tasks += 1
    try:
        async with _state.processing_lock:
            await _ws_broadcast({"type": "thinking"})

            result: dict[str, Any] = {"text": "", "elapsed": 0.0, "error": None}
            loop = asyncio.get_running_loop()

            def on_response(_: str, assistant: str, elapsed: float) -> None:
                result["text"] = assistant
                result["elapsed"] = elapsed

            def on_error(exc: Exception) -> None:
                result["error"] = str(exc)

            def on_audio_start() -> None:
                asyncio.run_coroutine_threadsafe(
                    _ws_broadcast({"type": "speaking", "state": "start"}), loop
                )

            def on_audio_end() -> None:
                asyncio.run_coroutine_threadsafe(
                    _ws_broadcast({"type": "speaking", "state": "end"}), loop
                )

            await asyncio.to_thread(
                _state.pipeline.process_turn,
                text,
                TurnCallbacks(
                    on_response=on_response,
                    on_error=on_error,
                    on_audio_start=on_audio_start,
                    on_audio_end=on_audio_end,
                ),
            )

            if result["error"]:
                await _ws_broadcast({"type": "error", "message": result["error"]})
            else:
                await _ws_broadcast({
                    "type": "response",
                    "text": result["text"],
                    "elapsed": round(result["elapsed"], 2),
                    "expression": _state.pipeline.current_expression,
                })
    finally:
        if is_owner:
            _state.pending_owner_tasks = max(0, _state.pending_owner_tasks - 1)


@router.get("/gemini-stats")
async def gemini_stats() -> dict:
    from utils.gemini_stats import get_stats
    return get_stats()


@router.delete("/history")
async def clear_history() -> dict:
    from server.state import pipeline
    if pipeline is None:
        return {"ok": False}
    pipeline.history = []
    from utils.history import save_history
    save_history(pipeline.history, pipeline.config.history_file)
    return {"ok": True}
