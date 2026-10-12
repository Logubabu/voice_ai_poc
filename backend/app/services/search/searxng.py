import time
from typing import List
import httpx
from app.utils.logging import logger
from app.services.search.provider import SearchProvider, SearchResult


class SearXNGProvider(SearchProvider):
    """SearXNG self-hosted open-source search engine provider implementation."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")

    async def search(
        self,
        query: str,
        max_results: int = 5,
        timeout: float = 5.0,
    ) -> List[SearchResult]:
        if not query or not query.strip():
            return []

        search_url = f"{self.base_url}/search"
        params = {"q": query.strip(), "format": "json"}

        start_time = time.time()
        logger.info(f"[SEARXNG] Requesting search for query: '{query.strip()}' at {search_url}")

        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                response = await client.get(search_url, params=params)
                duration_ms = (time.time() - start_time) * 1000

                if response.status_code != 200:
                    logger.error(f"[SEARXNG][ERROR] HTTP {response.status_code} ({duration_ms:.1f}ms): {response.text[:200]}")
                    return []

                data = response.json()
                raw_results = data.get("results", [])

                results: List[SearchResult] = []
                for item in raw_results[:max_results]:
                    title = item.get("title") or ""
                    url = item.get("url") or ""
                    snippet = item.get("content") or item.get("snippet") or ""
                    source = item.get("engine") or item.get("category") or "SearXNG"
                    published_at = item.get("publishedDate") or item.get("pubdate") or ""

                    if url:
                        results.append(
                            SearchResult(
                                title=title.strip(),
                                url=url.strip(),
                                snippet=snippet.strip(),
                                source=source.strip(),
                                published_at=published_at.strip(),
                            )
                        )

                logger.info(f"[SEARXNG] Completed in {duration_ms:.1f}ms: found {len(results)} results for query '{query}'")
                return results

        except httpx.TimeoutException:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"[SEARXNG][TIMEOUT] Timed out after {duration_ms:.1f}ms")
            return []
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"[SEARXNG][ERROR] Search failed after {duration_ms:.1f}ms: {e}")
            return []
