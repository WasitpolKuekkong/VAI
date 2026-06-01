from __future__ import annotations

import asyncio
from typing import Optional

from core.pipeline import VTuberPipeline

# Shared server state — initialized once in lifespan
pipeline: Optional[VTuberPipeline] = None
processing_lock = asyncio.Lock()  # one turn at a time (single-user VTuber)
