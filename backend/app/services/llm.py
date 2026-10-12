from typing import Any
from app.config import Config
from app.utils.logging import logger


def create_llm_service(cfg: Config, is_webcall: bool = True, system_instruction: str | None = None) -> Any:
    """Factory function to create LLM service adapter based on config.
    Strictly enforces LLM_PROVIDER without silent fallbacks.
    """
    provider = cfg.LLM_PROVIDER.lower()
    model = cfg.LLM_MODEL
    logger.info(f"[PIPELINE] Creating LLM (Provider: '{provider}', Model: '{model}', is_webcall: {is_webcall})")

    if provider in ("google", "gemini"):
        gemini_key = cfg.GEMINI_API_KEY or cfg.LLM_API_KEY
        if not gemini_key:
            logger.error("[LLM][FATAL] Gemini API key is not configured (GEMINI_API_KEY or LLM_API_KEY missing).")
            raise RuntimeError("Google Gemini LLM initialization failed: GEMINI_API_KEY is not configured.")
        try:
            from pipecat.services.google.llm import GoogleLLMService
            from app.tools.registry import global_tool_registry
            from app.tools.router import tool_router

            # Map deprecated or unavailable model names to active Gemini model
            SUPPORTED_MODELS = {"gemini-3.5-flash-lite", "gemini-3.8-flash"}
            gemini_model = model if model in SUPPORTED_MODELS else "gemini-3.5-flash-lite"
            if gemini_model != model:
                logger.warning(f"[LLM] Model '{model}' is deprecated or unavailable. Falling back to active model '{gemini_model}'.")

            sys_instruction = system_instruction or cfg.SYSTEM_PROMPT
            params = {}
            if hasattr(GoogleLLMService, "Settings"):
                params["settings"] = GoogleLLMService.Settings(
                    model=gemini_model,
                    system_instruction=sys_instruction,
                )
            else:
                params["model"] = gemini_model
            service = GoogleLLMService(api_key=gemini_key, **params)
            
            # Register Tool Registry function definitions & handlers on Gemini service if enabled
            tool_calling_enabled = cfg.WEBCALL_TOOL_CALLING_ENABLED if is_webcall else cfg.TOOL_CALLING_ENABLED
            enable_web = cfg.WEBCALL_WEB_SEARCH_ENABLED if is_webcall else cfg.WEB_SEARCH_ENABLED

            if tool_calling_enabled:
                global_tool_registry.register_tools_on_llm(service, enable_web_search=enable_web, router=tool_router)
                logger.info(f"[LLM] Provider: google | Model: {gemini_model} | WebCall Tools Registered (WebSearch Enabled: {enable_web})")
            else:
                logger.info(f"[LLM] Provider: google | Model: {gemini_model} | Tool calling DISABLED for session")

            return service
        except Exception as e:
            logger.exception(f"[LLM][FATAL] Google LLM initialization failed: {e}")
            raise RuntimeError(f"Google LLM initialization failed: {e}") from e

    if provider == "groq":
        groq_key = cfg.LLM_API_KEY or cfg.GROQ_API_KEY
        if not groq_key:
            logger.error("[LLM][FATAL] Groq LLM API key is not configured.")
            raise RuntimeError("Groq LLM initialization failed: API key missing.")
        try:
            from pipecat.services.groq.llm import GroqLLMService
            return GroqLLMService(api_key=groq_key, model=model)
        except Exception as e:
            logger.exception(f"[LLM][FATAL] Groq LLM initialization failed: {e}")
            raise RuntimeError(f"Groq LLM initialization failed: {e}") from e

    logger.error(f"[LLM][FATAL] Unsupported LLM provider: '{provider}'")
    raise RuntimeError(f"Unsupported LLM provider: '{provider}'")
