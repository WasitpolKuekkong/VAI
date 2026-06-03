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

    import server.state as state
    from server.state import pipeline, processing_lock

    if pipeline is None:
        await websocket.send_json({"type": "error", "message": "Server not ready"})
        await websocket.close()
        return

    state.active_ws.add(websocket)
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

            elif msg_type == "change_model":
                backend = (data.get("backend") or "").lower()
                model = (data.get("model") or "").strip()
                if model:
                    if backend == "gemini":
                        pipeline.config.google_aistudio_model = model
                    elif backend == "lmstudio":
                        pipeline.config.model_name = model
                    await _send_status(websocket, pipeline)

            elif msg_type == "toggle_audio":
                pipeline.config.audio_play_output = not pipeline.config.audio_play_output
                await _send_status(websocket, pipeline)

            elif msg_type == "set_tts":
                pitch = data.get("pitch")
                rate = data.get("rate")
                if pitch is not None:
                    pipeline.current_pitch = float(pitch)
                if rate is not None:
                    sign = "+" if float(rate) >= 0 else ""
                    pipeline.config.tts_rate = f"{sign}{int(float(rate))}%"
                await _send_status(websocket, pipeline)

            elif msg_type == "set_audio_output":
                device_id = data.get("device_id")
                if device_id is None:
                    pipeline.config.audio_output_device = None
                elif isinstance(device_id, int) and device_id >= 0:
                    pipeline.config.audio_output_device = device_id
                await _send_status(websocket, pipeline)

            elif msg_type == "connect_vts":
                await _handle_connect_vts(websocket, pipeline)

            elif msg_type == "disconnect_vts":
                await _handle_disconnect_vts(websocket, pipeline)

            elif msg_type == "set_restream_to_llm":
                state.restream_to_llm = bool(data.get("enabled", False))
                await _send_status(websocket, pipeline)

            elif msg_type == "connect_restream":
                await _handle_connect_restream(websocket, pipeline)

            elif msg_type == "disconnect_restream":
                await _handle_disconnect_restream(websocket, pipeline)

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    finally:
        state.active_ws.discard(websocket)


async def _handle_chat(websocket: WebSocket, user_text: str) -> None:
    import server.state as state
    from server.state import pipeline, processing_lock

    if pipeline is None:
        return

    # Web chat is always the owner (EiX2) — prefix so AI knows who's talking
    owner_name = "EiX2"
    labelled_text = f"[{owner_name}]: {user_text}"

    state.pending_owner_tasks += 1
    try:
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
                labelled_text,
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
                    "text": result["text"],
                    "elapsed": round(result["elapsed"], 2),
                    "expression": pipeline.current_expression,
                })
                await _send_status(websocket, pipeline)
    finally:
        state.pending_owner_tasks = max(0, state.pending_owner_tasks - 1)


async def _handle_connect_vts(websocket: WebSocket, pipeline: Any) -> None:
    from utils.vtuber_controller import initialize_vtuber_controller_sync, get_vtuber_controller
    ctrl = get_vtuber_controller()
    if ctrl and ctrl.websocket:
        await websocket.send_json({"type": "vts_status", "connected": True, "message": "Already connected"})
        return
    try:
        # Run in thread so websocket is created in _persistent_loop (same loop used by
        # trigger_expression / clear_expression — avoids "Future attached to a different loop")
        ctrl = await asyncio.to_thread(initialize_vtuber_controller_sync)
        connected = ctrl is not None
        await websocket.send_json({
            "type": "vts_status",
            "connected": connected,
            "message": "Connected to VTube Studio" if connected else "Failed — approve plugin in VTube Studio UI first",
        })
    except Exception as exc:
        await websocket.send_json({"type": "vts_status", "connected": False, "message": str(exc)})


async def _handle_disconnect_vts(websocket: WebSocket, pipeline: Any) -> None:
    from utils.vtuber_controller import cleanup_vtuber_controller_sync
    await asyncio.to_thread(cleanup_vtuber_controller_sync)
    pipeline.current_expression = "neutral"
    await websocket.send_json({"type": "vts_status", "connected": False, "message": "Disconnected"})


async def _handle_connect_restream(websocket: WebSocket, pipeline: Any) -> None:
    from utils.restream_client import is_connected, build_auth_url
    import server.state as state

    if is_connected():
        await websocket.send_json({
            "type": "restream_status",
            "connected": True,
            "message": "Already connected",
        })
        return

    cfg = pipeline.config
    if not cfg.restream_client_id or not cfg.restream_client_secret:
        await websocket.send_json({
            "type": "restream_status",
            "connected": False,
            "message": "Set RESTREAM_CLIENT_ID and RESTREAM_CLIENT_SECRET in .env",
        })
        return

    # Send auth URL — frontend opens it in a popup
    auth_url = build_auth_url(cfg.restream_client_id, cfg.restream_redirect_uri)
    await websocket.send_json({
        "type": "restream_auth",
        "url": auth_url,
        "message": "Opening Restream authorization…",
    })


async def _handle_disconnect_restream(websocket: WebSocket, pipeline: Any) -> None:
    import server.state as state
    from utils.restream_client import disconnect as rs_disconnect
    rs_disconnect()
    if state.restream_task and not state.restream_task.done():
        state.restream_task.cancel()
    state.restream_task = None
    state.restream_access_token = None
    await websocket.send_json({"type": "restream_status", "connected": False, "message": "Disconnected"})


async def _send_status(websocket: WebSocket, pipeline: Any) -> None:
    import server.state as state
    from backends.lmstudio import LMStudioBackend
    from utils.vtuber_controller import get_vtuber_controller
    cfg = pipeline.config
    lm = LMStudioBackend(
        base_url=cfg.lm_studio_base_url,
        model=cfg.model_name,
        temperature=cfg.temperature,
        max_tokens=cfg.max_tokens,
        timeout=cfg.request_timeout,
    )
    lm_healthy = await asyncio.to_thread(lm.is_healthy)
    ctrl = get_vtuber_controller()
    vts_connected = ctrl is not None and ctrl.websocket is not None
    await websocket.send_json({
        "type": "status",
        "backend": cfg.preferred_backend,
        "lmstudio_url": cfg.lm_studio_base_url,
        "lmstudio_healthy": lm_healthy,
        "gemini_model": cfg.google_aistudio_model or "gemini-2.5-flash",
        "lmstudio_model": cfg.model_name,
        "audio_enabled": cfg.audio_play_output,
        "audio_output_device": cfg.audio_output_device,
        "current_expression": pipeline.current_expression,
        "vts_connected": vts_connected,
        "restream_connected": __import__("utils.restream_client", fromlist=["is_connected"]).is_connected(),
        "restream_redirect_uri": cfg.restream_redirect_uri,
        "restream_to_llm": state.restream_to_llm,
        "restream_owner_names": cfg.restream_owner_names,
        "tts_pitch": pipeline.current_pitch,
        "tts_rate": int(float(cfg.tts_rate.replace("%", "").replace("+", "")) if cfg.tts_rate else 20),
    })
