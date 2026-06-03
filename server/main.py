from __future__ import annotations

import asyncio
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Ensure project root is in path when running as `uvicorn server.main:app`
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import load_settings
from core.pipeline import VTuberPipeline
from main import ensure_output_dirs
from rvc.applio_stub import prime_applio_worker
from utils.logger import logger
from utils.vtuber_controller import initialize_vtuber_controller, _run_in_loop

import server.state as state
from server.routers.chat import router as chat_router
from server.routers.config import router as config_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = load_settings()
    ensure_output_dirs(config)
    prime_applio_worker(config)

    try:
        _run_in_loop(initialize_vtuber_controller())
        logger.info("VTuber controller connected")
    except Exception as exc:
        logger.warning(f"VTuber init failed (non-fatal): {exc}")

    state.pipeline = VTuberPipeline(config)
    logger.info(
        f"VAI server ready | backend={config.preferred_backend} | "
        f"history={len(state.pipeline.history)} messages"
    )

    # Discord bot (optional — only starts when DISCORD_BOT_TOKEN is set)
    from utils.discord_bot import create_bot, start_bot
    import os
    discord_token = os.getenv("DISCORD_BOT_TOKEN", "")
    chat_channel_raw = os.getenv("DISCORD_CHAT_CHANNEL_ID", "")
    chat_channel_id = int(chat_channel_raw) if chat_channel_raw.isdigit() else None
    discord_bot = create_bot(
        pipeline=state.pipeline,
        token=discord_token,
        chat_channel_id=chat_channel_id,
        owner_name="EiX2",
        language="th",
    )
    if discord_bot:
        state.discord_task = asyncio.create_task(start_bot(discord_bot, discord_token))
        logger.info("Discord bot starting...")

    yield

    logger.info("VAI server shutting down")
    if state.discord_task and not state.discord_task.done():
        state.discord_task.cancel()


app = FastAPI(title="VAI API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(config_router)


@app.get("/")
async def root() -> dict:
    return {"service": "VAI API", "docs": "/docs"}
