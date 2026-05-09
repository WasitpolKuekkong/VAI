from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
env_file = BASE_DIR / ".env"
if env_file.exists():
    load_dotenv(env_file)


@dataclass(slots=True)
class AppConfig:
    lm_studio_base_url: str
    model_name: str
    personality_path: Path
    tts_output_dir: Path
    rvc_output_dir: Path
    history_file: Path
    tts_voice: str
    tts_rate: str
    tts_volume: str
    tts_output_format: str
    tts_default_speaker: str
    tts_default_pitch_semitones: float
    applio_path: Path
    applio_timeout: int
    rvc_model_pth: Path
    rvc_model_index: Path
    rvc_embedder_model: str
    rvc_embedder_custom: str
    rvc_f0_method: str
    audio_output_device: int | None
    audio_play_output: bool
    temperature: float
    max_tokens: int
    max_history_messages: int
    request_timeout: int


def _get_env(name: str, default: str) -> str:
    value = os.getenv(name)
    return value if value else default


def load_settings() -> AppConfig:
    return AppConfig(
        lm_studio_base_url=_get_env("LM_STUDIO_BASE_URL", "http://127.0.0.1:1234"),
        model_name=_get_env("LM_STUDIO_MODEL", "qwen/qwen3-14b"),
        personality_path=BASE_DIR / "config" / "personality.txt",
        tts_output_dir=BASE_DIR / "tts" / "output",
        rvc_output_dir=BASE_DIR / "rvc" / "output",
        history_file=BASE_DIR / "data" / "chat_history.json",
        tts_voice=_get_env("EDGE_TTS_VOICE", "th"),
        tts_rate=_get_env("EDGE_TTS_RATE", "+20%"),
        tts_volume=_get_env("EDGE_TTS_VOLUME", "+0%"),
        tts_output_format=_get_env("EDGE_TTS_FORMAT", "mp3"),
        tts_default_speaker=_get_env("EDGE_TTS_SPEAKER", "normal"),
        tts_default_pitch_semitones=float(_get_env("EDGE_TTS_PITCH_SEMITONES", "0")),
        applio_path=Path(_get_env("EDGE_APPLIO_PATH", r"C:\Users\MSI\Desktop\Applio")),
        applio_timeout=int(_get_env("EDGE_APPLIO_TIMEOUT", "120")),
        rvc_model_pth=Path(_get_env("RVC_MODEL_PTH", "")),
        rvc_model_index=Path(_get_env("RVC_MODEL_INDEX", "")),
        rvc_embedder_model=_get_env("RVC_EMBEDDER_MODEL", "contentvec"),
        rvc_embedder_custom=_get_env("RVC_EMBEDDER_CUSTOM", ""),
        rvc_f0_method=_get_env("RVC_F0_METHOD", "rmvpe"),
        audio_output_device=int(_get_env("AUDIO_OUTPUT_DEVICE", "-1")) if _get_env("AUDIO_OUTPUT_DEVICE", "-1") != "-1" else None,
        audio_play_output=_get_env("AUDIO_PLAY_OUTPUT", "true").lower() in ("true", "1", "yes"),
        temperature=float(_get_env("LM_STUDIO_TEMPERATURE", "0.7")),
        max_tokens=int(_get_env("LM_STUDIO_MAX_TOKENS", "512")),
        max_history_messages=int(_get_env("LM_STUDIO_HISTORY", "100")),
        request_timeout=int(_get_env("LM_STUDIO_TIMEOUT", "120")),
    )


def load_personality(path: Path) -> str:
    default_prompt = (
        "You are a friendly AI VTuber. Speak naturally, stay concise, and keep the tone lively. "
        "Respond in Thai unless the user clearly asks for another language."
    )
    if not path.exists():
        return default_prompt

    content = path.read_text(encoding="utf-8").strip()
    return content or default_prompt