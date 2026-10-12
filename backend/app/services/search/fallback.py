from typing import List
from app.utils.logging import logger
from app.services.search.provider import SearchProvider, SearchResult
from app.services.search.duckduckgo import DuckDuckGoProvider


class FallbackSearchProvider(SearchProvider):
    """Hybrid search provider that tries primary provider first, falling back to online DuckDuckGo search."""

    def __init__(self, primary_provider: SearchProvider, fallback_provider: SearchProvider = None):
        self.primary_provider = primary_provider
        self.fallback_provider = fallback_provider or DuckDuckGoProvider()

    async def search(
        self,
        query: str,
        max_results: int = 5,
        timeout: float = 5.0,
    ) -> List[SearchResult]:
        try:
            results = await self.primary_provider.search(query=query, max_results=max_results, timeout=timeout)
            if results:
                return results
            logger.info("[SEARCH-PROVIDER] Primary provider returned 0 results. Falling back to DuckDuckGo.")
        except Exception as e:
            logger.warning(f"[SEARCH-PROVIDER] Primary provider failed ({e}). Falling back to DuckDuckGo.")

        return await self.fallback_provider.search(query=query, max_results=max_results, timeout=timeout)
