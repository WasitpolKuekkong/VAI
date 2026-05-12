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
    restream_client_id: str
    restream_client_secret: str
    restream_redirect_uri: str
    voice_input_sample_rate: int
    voice_input_channels: int
    voice_input_duration_seconds: float
    voice_input_language: str
    voice_input_device_name: str
    voice_input_device: int | None
    vtuber_studio_api_url: str
    vtuber_studio_auth_token: str
    vtuber_studio_enabled: bool
    vtuber_studio_expression_hotkey: str
    vtuber_studio_clear_hotkey: str
    max_tokens: int
    max_history_messages: int
    request_timeout: int
    google_aistudio_api_key: str
    google_aistudio_model: str
    google_aistudio_enabled: bool
    preferred_backend: str


def _get_env(name: str, default: str) -> str:
    value = os.getenv(name)
    return value if value else default


def load_settings() -> AppConfig:
    return AppConfig(
        lm_studio_base_url=_get_env("LM_STUDIO_BASE_URL", "http://127.0.0.1:1234"),
        model_name=_get_env("LM_STUDIO_MODEL", "qwen/qwen3-8b"),
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
        restream_client_id=_get_env("RESTREAM_CLIENT_ID", ""),
        restream_client_secret=_get_env("RESTREAM_CLIENT_SECRET", ""),
        restream_redirect_uri=_get_env("RESTREAM_REDIRECT_URI", "http://localhost:8080/callback"),
        voice_input_sample_rate=int(_get_env("VOICE_INPUT_SAMPLE_RATE", "16000")),
        voice_input_channels=int(_get_env("VOICE_INPUT_CHANNELS", "1")),
        voice_input_duration_seconds=float(_get_env("VOICE_INPUT_DURATION_SECONDS", "5")),
        voice_input_language=_get_env("VOICE_INPUT_LANGUAGE", "th-TH"),
        voice_input_device_name=_get_env("VOICE_INPUT_DEVICE_NAME", ""),
        voice_input_device=int(_get_env("VOICE_INPUT_DEVICE", "-1")) if _get_env("VOICE_INPUT_DEVICE", "-1") != "-1" else None,
        vtuber_studio_api_url=_get_env("VTUBER_STUDIO_API_URL", "ws://localhost:8001"),
        vtuber_studio_auth_token=_get_env("VTUBER_STUDIO_AUTH_TOKEN", ""),
        vtuber_studio_enabled=_get_env("VTUBER_STUDIO_ENABLED", "true").lower() in ("true", "1", "yes"),
        vtuber_studio_expression_hotkey=_get_env("VTUBER_STUDIO_EXPRESSION_HOTKEY", "smile_happy"),
        vtuber_studio_clear_hotkey=_get_env("VTUBER_STUDIO_CLEAR_HOTKEY", "neutral"),
        max_tokens=int(_get_env("LM_STUDIO_MAX_TOKENS", "512")),
        max_history_messages=int(_get_env("LM_STUDIO_HISTORY", "100")),
        request_timeout=int(_get_env("LM_STUDIO_TIMEOUT", "120")),
        google_aistudio_api_key=_get_env("GOOGLE_AISTUDIO_API_KEY", ""),
        google_aistudio_model=_get_env("GOOGLE_AISTUDIO_MODEL", "gemini-2.5-flash"),
        google_aistudio_enabled=_get_env("GOOGLE_AISTUDIO_ENABLED", "false").lower() in ("true", "1", "yes"),
        preferred_backend=_get_env("PREFERRED_BACKEND", "gemini"),
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