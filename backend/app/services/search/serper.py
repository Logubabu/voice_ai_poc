import time
from typing import List
import httpx
from app.utils.logging import logger
from app.services.search.provider import SearchProvider, SearchResult


class SerperProvider(SearchProvider):
    """Search provider using Serper (Google Search API)."""

    def __init__(self, api_key: str, endpoint: str = "https://google.serper.dev/search"):
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
        logger.info(f"[SERPER] Requesting Google search for query: '{query}'")

        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json",
        }
        payload = {"q": query.strip(), "num": max_results}

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(self.endpoint, headers=headers, json=payload)
                duration_ms = (time.time() - start_time) * 1000

                if response.status_code != 200:
                    logger.error(f"[SERPER][ERROR] HTTP {response.status_code} ({duration_ms:.1f}ms): {response.text[:200]}")
                    return []

                data = response.json()
                organic = data.get("organic", [])
                results: List[SearchResult] = []

                for item in organic[:max_results]:
                    results.append(
                        SearchResult(
                            title=item.get("title", "").strip(),
                            url=item.get("link", "").strip(),
                            snippet=item.get("snippet", "").strip(),
                            source="Serper (Google)",
                            published_at=item.get("date", "") or "",
                        )
                    )

                logger.info(f"[SERPER] Returned {len(results)} results in {duration_ms:.1f}ms")
                return results

        except httpx.TimeoutException:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"[SERPER][TIMEOUT] Timed out after {duration_ms:.1f}ms")
            return []
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"[SERPER][ERROR] Search failed after {duration_ms:.1f}ms: {e}")
            return []
