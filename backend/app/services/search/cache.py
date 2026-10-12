import re
import time
from typing import List, Optional, Dict, Tuple
from app.services.search.provider import SearchResult
from app.utils.logging import logger


class SearchCache:
    """Short-lived TTL in-memory cache for search query results to minimize latency and API costs."""

    def __init__(self, ttl_seconds: float = 60.0):
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Tuple[float, List[SearchResult]]] = {}

    def _normalize_query(self, query: str) -> str:
        """Normalizes query string by lowercasing, stripping punctuation, and collapsing whitespace."""
        cleaned = re.sub(r"[^\w\s]", "", query.lower().strip())
        return re.sub(r"\s+", " ", cleaned)

    def get(self, query: str) -> Optional[List[SearchResult]]:
        """Retrieves cached search results if available and not expired."""
        key = self._normalize_query(query)
        if not key:
            return None

        if key in self._cache:
            timestamp, results = self._cache[key]
            if time.time() - timestamp <= self.ttl_seconds:
                logger.info(f"[SEARCH-CACHE] Cache HIT for query: '{query}' ({len(results)} items)")
                return results
            else:
                logger.info(f"[SEARCH-CACHE] Cache EXPIRED for query: '{query}'")
                del self._cache[key]
        return None

    def set(self, query: str, results: List[SearchResult]) -> None:
        """Caches search results with current timestamp."""
        key = self._normalize_query(query)
        if not key or not results:
            return
        self._cache[key] = (time.time(), results)
        logger.info(f"[SEARCH-CACHE] Cached {len(results)} results for query: '{query}' (TTL={self.ttl_seconds}s)")

    def clear(self) -> None:
        """Clears all cached items."""
        self._cache.clear()


search_cache = SearchCache(ttl_seconds=60.0)
