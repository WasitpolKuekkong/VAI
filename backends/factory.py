from __future__ import annotations

from config.settings import AppConfig
from backends.base import LLMBackend
from backends.gemini import GeminiBackend
from backends.lmstudio import LMStudioBackend
from utils.logger import logger


def _make_lmstudio(config: AppConfig) -> LMStudioBackend:
    return LMStudioBackend(
        base_url=config.lm_studio_base_url,
        model=config.model_name,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        timeout=config.request_timeout,
    )


def _make_gemini(config: AppConfig) -> GeminiBackend:
    return GeminiBackend(
        api_key=config.google_aistudio_api_key,
        model=config.google_aistudio_model,
    )


def get_backend(config: AppConfig) -> LLMBackend:
    """Return the configured backend, auto-falling back if primary is unreachable."""
    if config.preferred_backend.lower() == "lmstudio":
        backend = _make_lmstudio(config)
        if not backend.is_healthy():
            if config.google_aistudio_api_key:
                logger.warning(
                    f"LM Studio ไม่ตอบสนอง ({config.lm_studio_base_url}) → fallback Gemini อัตโนมัติ"
                )
                return _make_gemini(config)
            raise RuntimeError(
                f"LM Studio ไม่ตอบสนอง ({config.lm_studio_base_url}) "
                "และไม่มี GOOGLE_AISTUDIO_API_KEY สำหรับ fallback"
            )
        return backend

    return _make_gemini(config)


def get_quota_fallback(config: AppConfig, failed_backend_name: str) -> LLMBackend | None:
    """Return an alternative backend when the primary hits a quota/daily limit."""
    if failed_backend_name == "gemini":
        lm = _make_lmstudio(config)
        if lm.is_healthy():
            logger.warning("Gemini quota หมด → fallback LM Studio อัตโนมัติ")
            return lm
        logger.error("Gemini quota หมด และ LM Studio ไม่พร้อม — ไม่มี fallback")
        return None

    if failed_backend_name == "lmstudio" and config.google_aistudio_api_key:
        logger.warning("LM Studio quota/error → fallback Gemini อัตโนมัติ")
        return _make_gemini(config)

    return None
