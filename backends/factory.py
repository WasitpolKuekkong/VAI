from __future__ import annotations

from config.settings import AppConfig
from backends.base import LLMBackend
from backends.gemini import GeminiBackend
from backends.lmstudio import LMStudioBackend
from utils.logger import logger


def get_backend(config: AppConfig) -> LLMBackend:
    """Return the configured backend, auto-falling back to Gemini if LM Studio is unreachable."""
    if config.preferred_backend.lower() == "lmstudio":
        backend = LMStudioBackend(
            base_url=config.lm_studio_base_url,
            model=config.model_name,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            timeout=config.request_timeout,
        )
        if not backend.is_healthy():
            if config.google_aistudio_api_key:
                logger.warning(
                    f"LM Studio ไม่ตอบสนอง ({config.lm_studio_base_url}) → fallback Gemini อัตโนมัติ"
                )
                return GeminiBackend(
                    api_key=config.google_aistudio_api_key,
                    model=config.google_aistudio_model,
                )
            raise RuntimeError(
                f"LM Studio ไม่ตอบสนอง ({config.lm_studio_base_url}) "
                "และไม่มี GOOGLE_AISTUDIO_API_KEY สำหรับ fallback"
            )
        return backend

    return GeminiBackend(
        api_key=config.google_aistudio_api_key,
        model=config.google_aistudio_model,
    )
