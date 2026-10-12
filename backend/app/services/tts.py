from typing import Any
from app.config import Config
from app.utils.logging import logger


class AudioGenerationError(RuntimeError):
    """Raised when TTS service returns empty or invalid audio payloads."""
    pass


def validate_audio_bytes(audio: bytes, min_bytes: int = 10) -> bool:
    """Validates that generated audio bytes payload is non-empty and sufficient size."""
    if not audio:
        raise AudioGenerationError("TTS service returned empty audio data.")
    if len(audio) < min_bytes:
        raise AudioGenerationError(f"TTS service returned suspiciously small audio payload ({len(audio)} bytes).")
    return True


def create_tts_service(cfg: Config) -> Any:
    """Factory function to create TTS service adapter based on config.
    Strictly enforces TTS_PROVIDER without silent fallbacks.
    """
    provider = cfg.TTS_PROVIDER.lower()
    logger.info(f"[PIPELINE] Creating TTS (Provider: '{provider}')")

    if provider == "sarvam":
        sarvam_key = cfg.SARVAM_API_KEY or cfg.TTS_API_KEY
        if not sarvam_key:
            logger.error("[TTS][FATAL] Sarvam API key is not configured (SARVAM_API_KEY missing).")
            raise RuntimeError("Sarvam TTS initialization failed: SARVAM_API_KEY is not configured.")
        try:
            from pipecat.services.sarvam.tts import SarvamTTSService
            model = cfg.SARVAM_TTS_MODEL
            voice = cfg.SARVAM_TTS_VOICE
            settings = SarvamTTSService.Settings(model=model, voice=voice)
            service = SarvamTTSService(api_key=sarvam_key, settings=settings)
            logger.info(f"[TTS] Provider: sarvam | Voice: {voice} | Model: {model} | Initialized")
            return service
        except Exception as e:
            logger.exception(f"[TTS][FATAL] Sarvam TTS initialization failed: {e}")
            raise RuntimeError(f"Sarvam TTS initialization failed: {e}") from e

    if provider == "elevenlabs":
        el_key = cfg.ELEVENLABS_API_KEY or cfg.TTS_API_KEY
        if not el_key:
            logger.error("[TTS][FATAL] ElevenLabs API key is not configured (ELEVENLABS_API_KEY or TTS_API_KEY missing).")
            raise RuntimeError("ElevenLabs TTS initialization failed: ELEVENLABS_API_KEY is not configured.")
        try:
            from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
            model = getattr(cfg, "ELEVENLABS_MODEL", "eleven_flash_v2_5")
            if hasattr(ElevenLabsTTSService, "Settings"):
                settings = ElevenLabsTTSService.Settings(voice=cfg.ELEVENLABS_VOICE_ID, model=model)
                service = ElevenLabsTTSService(api_key=el_key, settings=settings)
            else:
                service = ElevenLabsTTSService(
                    api_key=el_key,
                    voice_id=cfg.ELEVENLABS_VOICE_ID,
                    model=model,
                )
            logger.info(f"[TTS] Provider: elevenlabs | Voice ID: {cfg.ELEVENLABS_VOICE_ID} | Model: {model} | Initialized")
            return service
        except Exception as e:
            logger.exception(f"[TTS][FATAL] ElevenLabs TTS initialization failed: {e}")
            raise RuntimeError(f"ElevenLabs TTS initialization failed: {e}") from e

    if provider == "groq":
        groq_key = cfg.TTS_API_KEY or cfg.GROQ_API_KEY
        if not groq_key:
            logger.error("[TTS][FATAL] Groq TTS API key is not configured.")
            raise RuntimeError("Groq TTS initialization failed: API key missing.")
        try:
            from pipecat.services.groq.tts import GroqTTSService
            service = GroqTTSService(api_key=groq_key)
            logger.info("[TTS] Provider: groq | Initialized")
            return service
        except Exception as e:
            logger.exception(f"[TTS][FATAL] Groq TTS initialization failed: {e}")
            raise RuntimeError(f"Groq TTS initialization failed: {e}") from e

    logger.error(f"[TTS][FATAL] Unsupported TTS provider: '{provider}'")
    raise RuntimeError(f"Unsupported TTS provider: '{provider}'")
