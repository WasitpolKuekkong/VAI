from __future__ import annotations

import time
from collections import deque

# Each entry: {"ts": float, "input_tokens": int, "output_tokens": int}
_log: deque[dict] = deque(maxlen=10_000)


def record(input_tokens: int, output_tokens: int) -> None:
    _log.append({"ts": time.time(), "input_tokens": input_tokens, "output_tokens": output_tokens})


def get_stats() -> dict:
    now = time.time()
    minute_ago = now - 60
    day_ago = now - 86_400

    last_minute = [e for e in _log if e["ts"] >= minute_ago]
    last_day = [e for e in _log if e["ts"] >= day_ago]

    return {
        "rpm": len(last_minute),
        "tpm": sum(e["input_tokens"] + e["output_tokens"] for e in last_minute),
        "rpd": len(last_day),
        "tpd": sum(e["input_tokens"] + e["output_tokens"] for e in last_day),
        "total_requests": len(_log),
    }
