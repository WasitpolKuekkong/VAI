from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from backends.factory import get_backend
from config.settings import AppConfig, load_personality
from core.capability_registry import CapabilityRegistry
from core.prompt_builder import build_system_prompt
from rvc.applio_stub import process_with_rvc
from tts.audio_player import find_vb_audio_device, play_audio
from tts.edge_tts_engine import SpeakerName, synthesize_speech
from utils.cleanup import cleanup_old_files
from utils.history import load_history, save_history
from utils.logger import logger
from utils.subtitle import schedule_expression_clear, schedule_subtitle_clear, write_subtitle
from utils.vtuber_controller import get_vtuber_controller, trigger_expression


@dataclass
class TurnCallbacks:
    on_response: Callable[[str, str, float], None] | None = None
    on_error: Callable[[Exception], None] | None = None
    on_audio_start: Callable[[], None] | None = None
    on_audio_end: Callable[[], None] | None = None


def build_messages(
    system_prompt: str,
    history: list[dict[str, str]],
    user_text: str,
) -> list[dict[str, str]]:
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_text})
    return messages


class VTuberPipeline:
    def __init__(
        self,
        config: AppConfig,
        registry: CapabilityRegistry | None = None,
    ) -> None:
        self.config = config
        self.registry = registry or CapabilityRegistry.default()
        personality_raw = load_personality(config.personality_path)
        self.system_prompt = build_system_prompt(personality_raw, self.registry)
        self.history: list[dict[str, str]] = load_history(config.history_file)
        self.current_speaker: SpeakerName = config.tts_default_speaker  # type: ignore[assignment]
        self.current_pitch: float = config.tts_default_pitch_semitones
        self.current_expression: str = "neutral"
        self._cached_audio_device: int | None = config.audio_output_device

    def process_turn(
        self,
        user_text: str,
        callbacks: TurnCallbacks | None = None,
    ) -> str:
        """Run one full pipeline turn. Returns assistant_text (empty on error)."""
        cb = callbacks or TurnCallbacks()
        turn_start = time.perf_counter()

        write_subtitle("*** คิดing ***")

        # LLM call with health-check fallback
        try:
            messages = build_messages(self.system_prompt, self.history, user_text)
            backend = get_backend(self.config)
            response = backend.chat(messages)
            assistant_text = response.text
            expression = response.expression
            if backend.name == "gemini":
                from utils.gemini_stats import record as _record_gemini
                _record_gemini(response.input_tokens, response.output_tokens)
        except Exception as exc:
            logger.error(f"LLM error ({self.config.preferred_backend}): {exc}")
            if cb.on_error:
                cb.on_error(exc)
            return ""

        if not assistant_text:
            logger.warning("Backend returned empty response")
            return ""

        # Update history
        self.history.append({"role": "user", "content": user_text})
        self.history.append({"role": "assistant", "content": assistant_text})
        self.history = self.history[-self.config.max_history_messages :]
        save_history(self.history, self.config.history_file)

        # Strip any (expression) tags the LLM may have embedded in the text
        tts_text = re.sub(r'\([^)]*\)\s*', '', assistant_text).strip()

        # TTS
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        tts_path = (
            self.config.tts_output_dir / f"reply_{timestamp}.{self.config.tts_output_format}"
        )
        try:
            tts_path = synthesize_speech(
                text=tts_text,
                output_path=tts_path,
                voice=self.config.tts_voice,
                rate=self.config.tts_rate,
                volume=self.config.tts_volume,
                speaker=self.current_speaker,
                pitch_semitones=self.current_pitch,
            )
        except Exception as exc:
            logger.error(f"TTS error: {exc}")
            if cb.on_error:
                cb.on_error(exc)
            return assistant_text

        cleanup_old_files(self.config.tts_output_dir, max_files=5)

        # RVC voice conversion (falls back to original TTS if Applio unavailable)
        rvc_ready_path = process_with_rvc(tts_path, self.config)

        # Always track expression for the UI badge, regardless of audio/VTS state
        effective_expression = expression or "smile_happy"
        self.current_expression = effective_expression

        # Audio playback + VTS expression trigger
        if self.config.audio_play_output:
            if self._cached_audio_device is None:
                self._cached_audio_device = find_vb_audio_device()
            device_id = self._cached_audio_device
            if device_id is not None:
                write_subtitle(tts_text)
                vtuber_ctrl = get_vtuber_controller()
                if vtuber_ctrl:
                    trigger_expression(effective_expression, controller=vtuber_ctrl)
                if cb.on_audio_start:
                    cb.on_audio_start()
                play_audio(rvc_ready_path, device_id=device_id, blocking=True)
                if cb.on_audio_end:
                    cb.on_audio_end()
                schedule_expression_clear(delay=2.0)
                threading.Timer(2.0, lambda: setattr(self, "current_expression", "neutral")).start()
                schedule_subtitle_clear(delay=5.0)
            else:
                logger.warning("Audio playback enabled but no output device found")
                schedule_subtitle_clear(delay=5.0)
        else:
            schedule_subtitle_clear(delay=5.0)

        elapsed = time.perf_counter() - turn_start
        logger.info(f"Turn time: {elapsed:.3f}s ({backend.name})")

        if cb.on_response:
            # Pass clean text (no expression tags) to display — history keeps the original
            cb.on_response(user_text, tts_text, elapsed)

        return tts_text
