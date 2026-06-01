from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from core.pipeline import TurnCallbacks
from utils.logger import logger

router = APIRouter()


@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket) -> None:
    await websocket.accept()

    from server.state import pipeline, processing_lock

    if pipeline is None:
        await websocket.send_json({"type": "error", "message": "Server not ready"})
        await websocket.close()
        return

    await _send_status(websocket, pipeline)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data: dict[str, Any] = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON"})
                continue

            msg_type = data.get("type")

            if msg_type == "chat":
                text = (data.get("text") or "").strip()
                if text:
                    await _handle_chat(websocket, text)

            elif msg_type == "switch_backend":
                backend = (data.get("backend") or "").lower()
                if backend in ("gemini", "lmstudio"):
                    pipeline.config.preferred_backend = backend
                    await _send_status(websocket, pipeline)

            elif msg_type == "toggle_audio":
                pipeline.config.audio_play_output = not pipeline.config.audio_play_output
                await _send_status(websocket, pipeline)

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")


async def _handle_chat(websocket: WebSocket, user_text: str) -> None:
    from server.state import pipeline, processing_lock

    if pipeline is None:
        return

    async with processing_lock:
        await websocket.send_json({"type": "thinking"})

        result: dict[str, Any] = {"text": "", "elapsed": 0.0, "error": None}
        loop = asyncio.get_running_loop()

        def on_response(_: str, assistant: str, elapsed: float) -> None:
            result["text"] = assistant
            result["elapsed"] = elapsed

        def on_error(exc: Exception) -> None:
            result["error"] = str(exc)

        def on_audio_start() -> None:
            asyncio.run_coroutine_threadsafe(
                websocket.send_json({"type": "speaking", "state": "start"}),
                loop,
            )

        def on_audio_end() -> None:
            asyncio.run_coroutine_threadsafe(
                websocket.send_json({"type": "speaking", "state": "end"}),
                loop,
            )

        await asyncio.to_thread(
            pipeline.process_turn,
            user_text,
            TurnCallbacks(
                on_response=on_response,
                on_error=on_error,
                on_audio_start=on_audio_start,
                on_audio_end=on_audio_end,
            ),
        )

        if result["error"]:
            await websocket.send_json({"type": "error", "message": result["error"]})
        else:
            await websocket.send_json({
                "type": "response",
                "user": user_text,
                "text": result["text"],
                "elapsed": round(result["elapsed"], 2),
            })


async def _send_status(websocket: WebSocket, pipeline: Any) -> None:
    from backends.lmstudio import LMStudioBackend
    cfg = pipeline.config
    lm = LMStudioBackend(
        base_url=cfg.lm_studio_base_url,
        model=cfg.model_name,
        temperature=cfg.temperature,
        max_tokens=cfg.max_tokens,
        timeout=cfg.request_timeout,
    )
    lm_healthy = await asyncio.to_thread(lm.is_healthy)
    await websocket.send_json({
        "type": "status",
        "backend": cfg.preferred_backend,
        "lmstudio_url": cfg.lm_studio_base_url,
        "lmstudio_healthy": lm_healthy,
        "gemini_model": cfg.google_aistudio_model or "gemini-2.5-flash",
        "lmstudio_model": cfg.model_name,
        "audio_enabled": cfg.audio_play_output,
    })
