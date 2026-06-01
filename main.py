from __future__ import annotations

import os
from pathlib import Path
from typing import cast

from backends.factory import get_backend
from backends.lmstudio import LMStudioBackend
from config.settings import AppConfig, load_settings
from core.pipeline import VTuberPipeline, TurnCallbacks
from rvc.applio_stub import prime_applio_worker
from tts.edge_tts_engine import SpeakerName
from utils.logger import logger
from utils.subtitle import write_subtitle
from utils.vtuber_controller import (
    initialize_vtuber_controller,
    _run_in_loop,
    list_hotkeys,
    get_vtuber_controller,
)


# ---------------------------------------------------------------------------
# Backward-compat exports — app.py imports these from main
# ---------------------------------------------------------------------------

def chat_with_backend(config: AppConfig, messages: list[dict[str, str]]) -> str:
    return get_backend(config).chat(messages).text


def chat_with_backend_and_expression(
    config: AppConfig, messages: list[dict[str, str]]
) -> tuple[str, str | None]:
    r = get_backend(config).chat(messages)
    return r.text, r.expression


def check_lm_studio_health(config: AppConfig, timeout: float = 3.0) -> bool:
    backend = LMStudioBackend(
        base_url=config.lm_studio_base_url,
        model=config.model_name,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        timeout=config.request_timeout,
    )
    return backend.is_healthy(ping_timeout=timeout)


def ensure_output_dirs(config: AppConfig) -> None:
    config.tts_output_dir.mkdir(parents=True, exist_ok=True)
    config.rvc_output_dir.mkdir(parents=True, exist_ok=True)
    config.history_file.parent.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    config = load_settings()
    ensure_output_dirs(config)
    prime_applio_worker(config)

    try:
        _run_in_loop(initialize_vtuber_controller())
        logger.info("VTuber controller connected")
    except Exception as e:
        logger.warning(f"VTuber init failed: {e}")

    pipeline = VTuberPipeline(config)

    print("AIVT ready")
    print(f"Backend: {config.preferred_backend.upper()}")
    if config.preferred_backend.lower() == "gemini":
        print(f"Model: {config.google_aistudio_model or 'gemini-2.5-flash'}")
    else:
        print(f"Model: {config.model_name}")
        print(f"LM Studio: {config.lm_studio_base_url}")
        if check_lm_studio_health(config):
            print("LM Studio: ✓ connected")
        else:
            fallback = "✓ Gemini fallback พร้อม" if config.google_aistudio_api_key else "✗ ไม่มี Gemini fallback"
            print(f"LM Studio: ✗ ไม่ตอบสนอง — {fallback}")

    print(f"Loaded {len(pipeline.history)} messages from history")
    print("Commands: /backend <gemini|lmstudio>, /speaker <name>, /pitch <value>, /speakers, /hotkeys\n")
    print(f"Current speaker: {pipeline.current_speaker}, pitch offset: {pipeline.current_pitch} semitones")

    while True:
        user_text = input("You: ").strip()
        write_subtitle("")
        if not user_text:
            continue
        if user_text.lower() in {"exit", "quit"}:
            break

        if user_text.startswith("/speaker "):
            _, sp = user_text.split(maxsplit=1)
            pipeline.current_speaker = cast(SpeakerName, sp.strip())
            print(f"Speaker set to: {pipeline.current_speaker}")
            continue

        if user_text.startswith("/backend "):
            try:
                _, backend_name = user_text.split(maxsplit=1)
                backend_name = backend_name.strip().lower()
                if backend_name not in ("gemini", "lmstudio"):
                    print("Usage: /backend <gemini|lmstudio>")
                    continue
                config.preferred_backend = backend_name
                if backend_name == "gemini":
                    print(f"✓ Switched to GEMINI (model: {config.google_aistudio_model or 'gemini-2.5-flash'})")
                else:
                    print(f"✓ Switched to LM STUDIO (model: {config.model_name})")
            except Exception as e:
                logger.error(f"Error switching backend: {e}")
                print("Usage: /backend <gemini|lmstudio>")
            continue

        if user_text.startswith("/pitch "):
            try:
                _, val = user_text.split(maxsplit=1)
                pipeline.current_pitch = float(val)
                print(f"Pitch offset set to: {pipeline.current_pitch} semitones")
            except Exception:
                print("Usage: /pitch <semitones>  (e.g. /pitch 2 or /pitch -1)")
            continue

        if user_text.strip() == "/speakers":
            print("Available speakers: normal, high, low, chipmunk, deep")
            continue

        if user_text.strip() == "/hotkeys":
            controller = get_vtuber_controller()
            if not controller:
                print("VTuber controller not initialized")
                continue
            hotkeys = list_hotkeys(controller)
            if not hotkeys:
                print("No hotkeys available or not connected")
            else:
                print("Available hotkeys:")
                for idx, hk in enumerate(hotkeys, start=1):
                    name = hk.get("name") or hk.get("fileName") or hk.get("file") or "<unnamed>"
                    print(f"{idx}: {name}  id={hk.get('hotkeyID')}")
            continue

        def _on_response(_: str, assistant: str, elapsed: float) -> None:
            print(f"AI: {assistant}\n")
            logger.info(f"Turn time: {elapsed:.3f}s")

        pipeline.process_turn(
            user_text,
            callbacks=TurnCallbacks(
                on_response=_on_response,
                on_error=lambda exc: print(f"Error: {exc}"),
            ),
        )


if __name__ == "__main__":
    os.chdir(Path(__file__).resolve().parent)
    main()
