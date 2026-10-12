from unittest.mock import patch, MagicMock, AsyncMock
import pytest
from app.services.search.provider import SearchResult
from app.services.search.duckduckgo import DuckDuckGoProvider
from app.services.search.tavily import TavilyProvider
from app.services.search.brave import BraveSearchProvider
from app.services.search.serper import SerperProvider
from app.services.search.bing import BingSearchProvider
from app.services.search.fallback import FallbackSearchProvider


@pytest.mark.asyncio
async def test_duckduckgo_empty_query():
    provider = DuckDuckGoProvider()
    results = await provider.search("")
    assert results == []


@pytest.mark.asyncio
async def test_tavily_provider_mock():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [{"title": "Tavily Result", "url": "https://tavily.com", "content": "Sample content"}]
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        provider = TavilyProvider(api_key="test_key")
        results = await provider.search("test query")
        assert len(results) == 1
        assert results[0].title == "Tavily Result"
        assert results[0].source == "Tavily"


@pytest.mark.asyncio
async def test_brave_provider_mock():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "web": {"results": [{"title": "Brave Result", "url": "https://brave.com", "description": "Brave desc"}]}
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        provider = BraveSearchProvider(api_key="test_key")
        results = await provider.search("test query")
        assert len(results) == 1
        assert results[0].title == "Brave Result"
        assert results[0].source == "Brave Search"


@pytest.mark.asyncio
async def test_serper_provider_mock():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "organic": [{"title": "Serper Result", "link": "https://google.com", "snippet": "Serper snippet"}]
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        provider = SerperProvider(api_key="test_key")
        results = await provider.search("test query")
        assert len(results) == 1
        assert results[0].title == "Serper Result"
        assert results[0].source == "Serper (Google)"


@pytest.mark.asyncio
async def test_bing_provider_mock():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "webPages": {"value": [{"name": "Bing Result", "url": "https://bing.com", "snippet": "Bing snippet"}]}
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        provider = BingSearchProvider(api_key="test_key")
        results = await provider.search("test query")
        assert len(results) == 1
        assert results[0].title == "Bing Result"
        assert results[0].source == "Bing Search"


@pytest.mark.asyncio
async def test_fallback_search_provider():
    class FailingProvider:
        async def search(self, query, max_results=5, timeout=5.0):
            raise RuntimeError("Primary provider failed")

    class WorkingProvider:
        async def search(self, query, max_results=5, timeout=5.0):
            return [SearchResult(title="Fallback Result", url="https://fallback.com", snippet="Fallback snippet")]

    fallback_provider = FallbackSearchProvider(primary_provider=FailingProvider(), fallback_provider=WorkingProvider())
    results = await fallback_provider.search("test query")
    assert len(results) == 1
    assert results[0].title == "Fallback Result"
