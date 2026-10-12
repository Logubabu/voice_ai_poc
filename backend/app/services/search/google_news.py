import time
import html
import xml.etree.ElementTree as ET
from typing import List
from urllib.parse import quote
import httpx
from bs4 import BeautifulSoup

from app.utils.logging import logger
from app.services.search.provider import SearchProvider, SearchResult


class GoogleNewsProvider(SearchProvider):
    """Real-time online news search provider powered by Google News RSS."""

    def __init__(self, hl: str = "en-IN", gl: str = "IN", ceid: str = "IN:en"):
        self.hl = hl
        self.gl = gl
        self.ceid = ceid

    async def search(
        self,
        query: str,
        max_results: int = 5,
        timeout: float = 5.0,
    ) -> List[SearchResult]:
        if not query or not query.strip():
            return []

        start_time = time.time()
        clean_query = query.strip()
        encoded = quote(clean_query)
        url = f"https://news.google.com/rss/search?q={encoded}&hl={self.hl}&gl={self.gl}&ceid={self.ceid}"

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }

        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                response = await client.get(url, headers=headers)
                duration_ms = (time.time() - start_time) * 1000

                if response.status_code != 200:
                    logger.error(f"[GOOGLE-NEWS][ERROR] HTTP {response.status_code} ({duration_ms:.1f}ms)")
                    return []

                root = ET.fromstring(response.text)
                items = root.findall(".//item")
                results: List[SearchResult] = []

                for item in items[:max_results]:
                    title_elem = item.find("title")
                    link_elem = item.find("link")
                    pub_elem = item.find("pubDate")
                    desc_elem = item.find("description")

                    title = html.unescape(title_elem.text.strip()) if title_elem is not None and title_elem.text else ""
                    link = link_elem.text.strip() if link_elem is not None and link_elem.text else ""
                    pub_date = pub_elem.text.strip() if pub_elem is not None and pub_elem.text else ""

                    snippet = ""
                    if desc_elem is not None and desc_elem.text:
                        clean_desc = html.unescape(desc_elem.text)
                        snippet = BeautifulSoup(clean_desc, "html.parser").get_text(strip=True)

                    if not snippet:
                        snippet = title

                    if title and link:
                        results.append(
                            SearchResult(
                                title=title,
                                url=link,
                                snippet=snippet,
                                source="Google News",
                                published_at=pub_date,
                            )
                        )

                logger.info(f"[GOOGLE-NEWS] Found {len(results)} results in {duration_ms:.1f}ms for '{clean_query}'")
                return results

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"[GOOGLE-NEWS][ERROR] Search failed after {duration_ms:.1f}ms: {e}")
            return []
