from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional

from utils.logger import logger

_SUBTITLE_FILE = Path(__file__).resolve().parent.parent / "subtitle.txt"
_SUBTITLE_LOCK = threading.Lock()
_SUBTITLE_TIMER: Optional[threading.Timer] = None
_EXPRESSION_TIMER: Optional[threading.Timer] = None
_EXPRESSION_LOCK = threading.Lock()


def write_subtitle(text: str) -> None:
    with _SUBTITLE_LOCK:
        try:
            _SUBTITLE_FILE.write_text(text + "\n", encoding="utf-8")
        except Exception as exc:
            logger.error(f"Failed to write subtitle: {exc}")


def clear_subtitle() -> None:
    with _SUBTITLE_LOCK:
        try:
            _SUBTITLE_FILE.write_text("", encoding="utf-8")
        except Exception as exc:
            logger.error(f"Failed to clear subtitle: {exc}")


def schedule_subtitle_clear(delay: float = 5.0) -> None:
    global _SUBTITLE_TIMER
    with _SUBTITLE_LOCK:
        if _SUBTITLE_TIMER:
            try:
                _SUBTITLE_TIMER.cancel()
            except Exception:
                pass
        _SUBTITLE_TIMER = threading.Timer(delay, clear_subtitle)
        _SUBTITLE_TIMER.daemon = True
        _SUBTITLE_TIMER.start()


def schedule_expression_clear(delay: float = 2.0) -> None:
    global _EXPRESSION_TIMER
    # Lazy import to avoid circular dependency
    from utils.vtuber_controller import get_vtuber_controller, clear_expression  # noqa: PLC0415

    with _EXPRESSION_LOCK:
        if _EXPRESSION_TIMER:
            try:
                _EXPRESSION_TIMER.cancel()
            except Exception:
                pass
        controller = get_vtuber_controller()
        if controller:
            _EXPRESSION_TIMER = threading.Timer(
                delay, lambda: clear_expression(controller=controller)
            )
            _EXPRESSION_TIMER.daemon = True
            _EXPRESSION_TIMER.start()
