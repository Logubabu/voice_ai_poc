from abc import ABC, abstractmethod
from typing import List, Dict, Any
from pydantic import BaseModel


class SearchResult(BaseModel):
    """Normalized search result model."""
    title: str = ""
    url: str = ""
    snippet: str = ""
    source: str = ""
    published_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "source": self.source,
            "published_at": self.published_at,
        }


class SearchProvider(ABC):
    """Abstract Base Class for search engine providers."""

    @abstractmethod
    async def search(
        self,
        query: str,
        max_results: int = 5,
        timeout: float = 5.0,
    ) -> List[SearchResult]:
        """Perform search and return normalized SearchResult objects."""
        pass
