from __future__ import annotations

import json
from pathlib import Path


def load_history(history_file: Path) -> list[dict[str, str]]:
    """Load chat history from JSON file."""
    if not history_file.exists():
        return []
    
    try:
        with open(history_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def save_history(history: list[dict[str, str]], history_file: Path) -> None:
    """Save chat history to JSON file."""
    history_file.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(history_file, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except IOError as exc:
        print(f"Warning: Could not save history: {exc}")
