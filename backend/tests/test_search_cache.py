import time
from app.services.search.cache import SearchCache
from app.services.search.provider import SearchResult


def test_search_cache_hit_and_miss():
    cache = SearchCache(ttl_seconds=2.0)
    query = "current Bitcoin price USD"
    results = [
        SearchResult(title="BTC Price", url="https://example.com/btc", snippet="BTC is $65,000", source="Test")
    ]

    # Initially cache miss
    assert cache.get(query) is None

    # Set cache
    cache.set(query, results)

    # Cache hit (even with different capitalization or extra whitespace)
    cached = cache.get("  CURRENT bitcoin PRICE usd  ")
    assert cached is not None
    assert len(cached) == 1
    assert cached[0].title == "BTC Price"


def test_search_cache_expiration():
    cache = SearchCache(ttl_seconds=0.1)
    query = "NVIDIA stock news"
    results = [SearchResult(title="NVIDIA", url="https://example.com/nvda", snippet="Stock up 5%")]

    cache.set(query, results)
    time.sleep(0.2)

    # After TTL, cache miss
    assert cache.get(query) is None
