from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Optional

from core.pipeline import VTuberPipeline

if TYPE_CHECKING:
    from fastapi import WebSocket

# Shared server state — initialized once in lifespan
pipeline: Optional[VTuberPipeline] = None
processing_lock = asyncio.Lock()

# Active frontend WebSocket connections (for broadcasting)
active_ws: set["WebSocket"] = set()

# Restream
restream_task: Optional[asyncio.Task] = None
restream_access_token: Optional[str] = None

# Discord
discord_task: Optional[asyncio.Task] = None

# Restream → LLM forwarding
restream_to_llm: bool = False
# Tracks owner tasks queued/running — viewers skip when this > 0
pending_owner_tasks: int = 0
