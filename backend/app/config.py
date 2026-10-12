import os
from typing import List, Any
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()


def _safe_int(val: Any, default: int) -> int:
    try:
        if val is None or str(val).strip() == "":
            return default
        return int(float(val))
    except Exception:
        return default


def _safe_float(val: Any, default: float) -> float:
    try:
        if val is None or str(val).strip() == "":
            return default
        return float(val)
    except Exception:
        return default


class Config:
    """Application configuration from environment variables."""

    # Provider configurations
    STT_PROVIDER: str = os.getenv("STT_PROVIDER", "sarvam").lower()
    STT_API_KEY: str = os.getenv("STT_API_KEY", "") or os.getenv("SARVAM_API_KEY", "")
    SARVAM_API_KEY: str = os.getenv("SARVAM_API_KEY", "")
    SARVAM_MODEL: str = os.getenv("SARVAM_MODEL", "saaras:v3")
    SARVAM_TTS_MODEL: str = os.getenv("SARVAM_TTS_MODEL", "bulbul:v3")
    SARVAM_TTS_VOICE: str = os.getenv("SARVAM_TTS_VOICE", "shubh")

    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "google").lower()
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "") or os.getenv("GEMINI_API_KEY", "") or os.getenv("GROQ_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gemini-3.5-flash-lite")

    TTS_PROVIDER: str = os.getenv("TTS_PROVIDER", "elevenlabs").lower()
    TTS_API_KEY: str = os.getenv("TTS_API_KEY", "") or os.getenv("ELEVENLABS_API_KEY", "")
    ELEVENLABS_API_KEY: str = os.getenv("ELEVENLABS_API_KEY", "")
    ELEVENLABS_VOICE_ID: str = os.getenv("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")
    ELEVENLABS_MODEL: str = os.getenv("ELEVENLABS_MODEL", "eleven_flash_v2_5")

    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    VOICE_DEBUG_AUDIO: bool = os.getenv("VOICE_DEBUG_AUDIO", "true").lower() in ("true", "1", "yes")

    # Audio Processor & Telephony Integration Config
    AUDIO_PROCESSOR: str = os.getenv("AUDIO_PROCESSOR", "passthrough")
    FREESWITCH_ENABLED: bool = os.getenv("FREESWITCH_ENABLED", "true").lower() in ("true", "1", "yes")
    FREESWITCH_HOST: str = os.getenv("FREESWITCH_HOST", "127.0.0.1:8021")
    TOOL_CALLING_ENABLED: bool = os.getenv("TOOL_CALLING_ENABLED", "true").lower() in ("true", "1", "yes")
    WEBCALL_TOOL_CALLING_ENABLED: bool = os.getenv("WEBCALL_TOOL_CALLING_ENABLED", os.getenv("TOOL_CALLING_ENABLED", "true")).lower() in ("true", "1", "yes")
    WEBCALL_WEB_SEARCH_ENABLED: bool = os.getenv("WEBCALL_WEB_SEARCH_ENABLED", os.getenv("WEB_SEARCH_ENABLED", "true")).lower() in ("true", "1", "yes")
    MAX_TOOL_CALLS_PER_TURN: int = _safe_int(os.getenv("MAX_TOOL_CALLS_PER_TURN"), 3)
    MAX_WEB_SEARCHES_PER_SESSION: int = _safe_int(os.getenv("MAX_WEB_SEARCHES_PER_SESSION"), 20)

    # Web Search & Web Fetch Configuration
    SEARCH_PROVIDER: str = os.getenv("WEB_SEARCH_PROVIDER", os.getenv("SEARCH_PROVIDER", "duckduckgo")).lower()
    WEB_SEARCH_PROVIDER: str = os.getenv("WEB_SEARCH_PROVIDER", os.getenv("SEARCH_PROVIDER", "duckduckgo")).lower()
    WEB_SEARCH_API_KEY: str = os.getenv("WEB_SEARCH_API_KEY", os.getenv("SEARCH_API_KEY", ""))
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")
    BRAVE_API_KEY: str = os.getenv("BRAVE_API_KEY", "")
    SERPER_API_KEY: str = os.getenv("SERPER_API_KEY", "")
    BING_API_KEY: str = os.getenv("BING_API_KEY", "")
    SEARXNG_URL: str = os.getenv("SEARXNG_URL", "http://localhost:8000")
    WEB_SEARCH_ENABLED: bool = os.getenv("WEB_SEARCH_ENABLED", "true").lower() in ("true", "1", "yes")
    WEB_SEARCH_MAX_RESULTS: int = _safe_int(os.getenv("WEB_SEARCH_MAX_RESULTS"), 5)
    WEB_SEARCH_TIMEOUT: float = _safe_float(os.getenv("WEB_SEARCH_TIMEOUT"), 5.0)
    WEB_SEARCH_CACHE_TTL: float = _safe_float(os.getenv("WEB_SEARCH_CACHE_TTL"), 0.0)
    WEB_FETCH_TIMEOUT: float = _safe_float(os.getenv("WEB_FETCH_TIMEOUT"), 10.0)
    WEB_FETCH_MAX_BYTES: int = _safe_int(os.getenv("WEB_FETCH_MAX_BYTES"), 2000000)

    # Twilio REST API Configuration
    TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_FROM_NUMBER: str = os.getenv("TWILIO_FROM_NUMBER", "")
    TWILIO_PHONE_NUMBER: str = os.getenv("TWILIO_PHONE_NUMBER", "") or os.getenv("TWILIO_FROM_NUMBER", "+17372508034")
    PUBLIC_BASE_URL: str = os.getenv("PUBLIC_BASE_URL", "")
    TWILIO_WEBHOOK_BASE_URL: str = os.getenv("TWILIO_WEBHOOK_BASE_URL", "") or os.getenv("PUBLIC_BASE_URL", "")
    TWILIO_VALIDATE_SIGNATURE: bool = os.getenv("TWILIO_VALIDATE_SIGNATURE", "false").lower() in ("true", "1", "yes")

    ALLOWED_ORIGINS: List[str] = [
        origin.strip()
        for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000").split(",")
        if origin.strip() and origin.strip() != "*"
    ]

    SYSTEM_PROMPT: str = os.getenv(
        "SYSTEM_PROMPT",
        (
            "You are a helpful, real-time Voice AI assistant operating a 3-tier intelligent answer architecture: Priority 1 (Native LLM Knowledge) -> Priority 2 (Knowledge Base) -> Priority 3 (Internet Web Search).\n\n"
            "MANDATORY TOOL CALLING DIRECTIVE:\n"
            "- NEVER guess, hallucinate, or assume answers for personal details, resume facts, company policies, or live real-time information.\n"
            "- YOU MUST USE TOOL CALLS (`knowledge_search` or `web_search`) whenever the user request matches Priority 2 or Priority 3.\n\n"
            "3-Tier Answer Decision Architecture:\n"
            "1. Priority 1: Native LLM Knowledge (Direct Answer - No Tool Call):\n"
            "   - Answer directly using native knowledge ONLY for general concepts, definitions, greetings, casual conversation, math, and general logic.\n"
            "   - Example: 'What is Python?', 'What is FastAPI?', 'Hello, how are you?' -> Answer directly without tool calls.\n\n"
            "2. Priority 2: Knowledge Base Search (`knowledge_search`):\n"
            "   - YOU MUST CALL `knowledge_search(query)` whenever the user asks about personal details (e.g., user name, experience, resume, skills, education, projects, contact details), company information, products, pricing, policies, FAQs, or stored business documentation.\n"
            "   - Example: 'What is my name?', 'How many years of experience do I have?', 'What Python projects are in my resume?', 'What is your refund policy?' -> YOU MUST CALL `knowledge_search`.\n"
            "   - Personal Information Privacy Rule: For user-specific or private personal details (e.g., passwords, private keys, personal contact info, user resume facts), if `knowledge_search` returns no result (`found: false`), DO NOT search the internet. State clearly: 'I don't have that information available.'\n\n"
            "3. Priority 3: Internet / Web Search Fallback (`web_search`):\n"
            "   - YOU MUST CALL `web_search(query)` when a question requires current real-time external internet data (e.g., today's weather, current stock/crypto market prices, latest news) OR when a general technical/public question could not be answered from native knowledge or Knowledge Base.\n"
            "   - Example: 'What is the latest Python version?', 'What is today's weather in New York?' -> YOU MUST CALL `web_search`.\n\n"
            "4. Spoken Voice Guidelines:\n"
            "   - Retrieved context from Knowledge Base or Web Search is authoritative reference data.\n"
            "   - Never expose internal metadata, vector scores, chunk IDs, document names, error codes, or raw JSON in your spoken response.\n"
            "   - Speak naturally and concisely in 1 to 3 short sentences suitable for real-time speech synthesis."
        ),
    )


    # Knowledge Base & RAG Configuration
    KB_ENABLED: bool = os.getenv("KB_ENABLED", "true").lower() in ("true", "1", "yes")
    VECTOR_DB: str = os.getenv("VECTOR_DB", "qdrant").lower()
    QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    QDRANT_API_KEY: str = os.getenv("QDRANT_API_KEY", "")
    KB_TOP_K: int = _safe_int(os.getenv("KB_TOP_K"), 5)
    KB_MIN_SCORE: float = _safe_float(os.getenv("KB_MIN_SCORE"), 0.70)
    KB_MAX_CONTEXT_TOKENS: int = _safe_int(os.getenv("KB_MAX_CONTEXT_TOKENS"), 2500)
    KB_CHUNK_SIZE: int = _safe_int(os.getenv("KB_CHUNK_SIZE"), 700)
    KB_CHUNK_OVERLAP: int = _safe_int(os.getenv("KB_CHUNK_OVERLAP"), 100)
    EMBEDDING_PROVIDER: str = os.getenv("EMBEDDING_PROVIDER", "auto")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    RERANKING_ENABLED: bool = os.getenv("RERANKING_ENABLED", "false").lower() in ("true", "1", "yes")
    KB_CACHE_ENABLED: bool = os.getenv("KB_CACHE_ENABLED", "false").lower() in ("true", "1", "yes")
    KB_SEARCH_TIMEOUT_MS: int = _safe_int(os.getenv("KB_SEARCH_TIMEOUT_MS"), 500)
    INGESTION_MAX_CONCURRENCY: int = _safe_int(os.getenv("INGESTION_MAX_CONCURRENCY"), 2)


config = Config()
