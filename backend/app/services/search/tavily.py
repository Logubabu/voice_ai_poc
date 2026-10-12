import time
from typing import List
import httpx
from app.utils.logging import logger
from app.services.search.provider import SearchProvider, SearchResult


class TavilyProvider(SearchProvider):
    """Search provider using Tavily Search API."""

    def __init__(self, api_key: str, endpoint: str = "https://api.tavily.com/search"):
        self.api_key = api_key
        self.endpoint = endpoint

    async def search(
        self,
        query: str,
        max_results: int = 5,
        timeout: float = 5.0,
    ) -> List[SearchResult]:
        if not query or not query.strip():
            return []

        start_time = time.time()
        logger.info(f"[TAVILY] Requesting web search for query: '{query}'")

        payload = {
            "api_key": self.api_key,
            "query": query.strip(),
            "max_results": max_results,
            "search_depth": "basic",
            "include_answer": False,
        }

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(self.endpoint, json=payload)
                duration_ms = (time.time() - start_time) * 1000

                if response.status_code != 200:
                    logger.error(f"[TAVILY][ERROR] HTTP {response.status_code} ({duration_ms:.1f}ms): {response.text[:200]}")
                    return []

                data = response.json()
                raw_results = data.get("results", [])
                results: List[SearchResult] = []

                for item in raw_results[:max_results]:
                    results.append(
                        SearchResult(
                            title=item.get("title", "").strip(),
                            url=item.get("url", "").strip(),
                            snippet=item.get("content", "").strip() or item.get("snippet", "").strip(),
                            source="Tavily",
                            published_at=item.get("published_date", "") or "",
                        )
                    )

                logger.info(f"[TAVILY] Returned {len(results)} results in {duration_ms:.1f}ms")
                return results

        except httpx.TimeoutException:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"[TAVILY][TIMEOUT] Timed out after {duration_ms:.1f}ms")
            return []
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"[TAVILY][ERROR] Search failed after {duration_ms:.1f}ms: {e}")
            return []
