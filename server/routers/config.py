from __future__ import annotations

import asyncio

from fastapi import APIRouter
from pydantic import BaseModel

from backends.lmstudio import LMStudioBackend

router = APIRouter(prefix="/api")


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


@router.delete("/history")
async def clear_history() -> dict:
    from server.state import pipeline
    if pipeline is None:
        return {"ok": False}
    pipeline.history = []
    from utils.history import save_history
    save_history(pipeline.history, pipeline.config.history_file)
    return {"ok": True}
