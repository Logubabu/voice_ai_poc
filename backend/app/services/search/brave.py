import time
from typing import List
import httpx
from app.utils.logging import logger
from app.services.search.provider import SearchProvider, SearchResult


class BraveSearchProvider(SearchProvider):
    """Search provider using Brave Search API."""

    def __init__(self, api_key: str, endpoint: str = "https://api.search.brave.com/res/v1/web/search"):
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
        logger.info(f"[BRAVE] Requesting web search for query: '{query}'")

        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": self.api_key,
        }
        params = {"q": query.strip(), "count": max_results}

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(self.endpoint, headers=headers, params=params)
                duration_ms = (time.time() - start_time) * 1000

                if response.status_code != 200:
                    logger.error(f"[BRAVE][ERROR] HTTP {response.status_code} ({duration_ms:.1f}ms): {response.text[:200]}")
                    return []

                data = response.json()
                web_results = data.get("web", {}).get("results", [])
                results: List[SearchResult] = []

                for item in web_results[:max_results]:
                    results.append(
                        SearchResult(
                            title=item.get("title", "").strip(),
                            url=item.get("url", "").strip(),
                            snippet=item.get("description", "").strip(),
                            source="Brave Search",
                            published_at=item.get("page_age", "") or "",
                        )
                    )

                logger.info(f"[BRAVE] Returned {len(results)} results in {duration_ms:.1f}ms")
                return results

        except httpx.TimeoutException:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"[BRAVE][TIMEOUT] Timed out after {duration_ms:.1f}ms")
            return []
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"[BRAVE][ERROR] Search failed after {duration_ms:.1f}ms: {e}")
            return []
