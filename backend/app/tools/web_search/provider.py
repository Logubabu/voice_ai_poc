from typing import Optional, Any

from app.config import config
from app.utils.logging import logger
from app.services.search.provider import SearchProvider
from app.services.search.duckduckgo import DuckDuckGoProvider
from app.services.search.searxng import SearXNGProvider
from app.services.search.tavily import TavilyProvider
from app.services.search.brave import BraveSearchProvider
from app.services.search.serper import SerperProvider
from app.services.search.bing import BingSearchProvider
from app.services.search.fallback import FallbackSearchProvider


def create_search_provider(cfg: Optional[Any] = None) -> SearchProvider:
    """Factory function to instantiate configured search provider abstraction."""
    app_cfg = cfg or config
    provider_type = (
        getattr(app_cfg, "WEB_SEARCH_PROVIDER", None)
        or getattr(app_cfg, "SEARCH_PROVIDER", "duckduckgo")
    ).lower().strip()

    api_key = getattr(app_cfg, "WEB_SEARCH_API_KEY", "") or getattr(app_cfg, "SEARCH_API_KEY", "")
    searxng_url = getattr(app_cfg, "SEARXNG_URL", "http://localhost:8000")

    if provider_type == "tavily":
        tavily_key = api_key or getattr(app_cfg, "TAVILY_API_KEY", "")
        if tavily_key:
            logger.info("[SEARCH-PROVIDER] Initializing TavilyProvider.")
            return TavilyProvider(api_key=tavily_key)
        logger.warning("[SEARCH-PROVIDER] Tavily requested but API key missing. Falling back to DuckDuckGo.")

    elif provider_type == "brave":
        brave_key = api_key or getattr(app_cfg, "BRAVE_API_KEY", "")
        if brave_key:
            logger.info("[SEARCH-PROVIDER] Initializing BraveSearchProvider.")
            return BraveSearchProvider(api_key=brave_key)
        logger.warning("[SEARCH-PROVIDER] Brave requested but API key missing. Falling back to DuckDuckGo.")

    elif provider_type == "serper":
        serper_key = api_key or getattr(app_cfg, "SERPER_API_KEY", "")
        if serper_key:
            logger.info("[SEARCH-PROVIDER] Initializing SerperProvider.")
            return SerperProvider(api_key=serper_key)
        logger.warning("[SEARCH-PROVIDER] Serper requested but API key missing. Falling back to DuckDuckGo.")

    elif provider_type == "bing":
        bing_key = api_key or getattr(app_cfg, "BING_API_KEY", "")
        if bing_key:
            logger.info("[SEARCH-PROVIDER] Initializing BingSearchProvider.")
            return BingSearchProvider(api_key=bing_key)
        logger.warning("[SEARCH-PROVIDER] Bing requested but API key missing. Falling back to DuckDuckGo.")

    elif provider_type == "searxng":
        logger.info(f"[SEARCH-PROVIDER] Initializing SearXNGProvider ({searxng_url}) with fallback.")
        return FallbackSearchProvider(
            primary_provider=SearXNGProvider(base_url=searxng_url),
            fallback_provider=DuckDuckGoProvider(),
        )

    logger.info("[SEARCH-PROVIDER] Initializing default DuckDuckGo search provider.")
    return DuckDuckGoProvider()
