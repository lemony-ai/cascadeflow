"""Test suite for response caching."""

import time

import pytest

from cascadeflow.utils.caching import ResponseCache


class TestResponseCache:
    """Test response cache."""

    def test_basic_set_get(self):
        cache = ResponseCache()
        response = {"content": "4", "cost": 0.0}

        cache.set("What is 2+2?", response)
        cached = cache.get("What is 2+2?")

        assert cached is not None
        assert cached["content"] == "4"

    def test_cache_miss(self):
        cache = ResponseCache()
        cached = cache.get("Non-existent query")

        assert cached is None

    def test_ttl_expiration(self):
        cache = ResponseCache(default_ttl=1)
        response = {"content": "test"}

        cache.set("Test query", response, ttl=1)

        # Should be cached
        assert cache.get("Test query") is not None

        # Wait for expiration
        time.sleep(1.1)

        # Should be expired
        assert cache.get("Test query") is None

    def test_lru_eviction(self):
        cache = ResponseCache(max_size=2)

        cache.set("query1", {"content": "1"})
        cache.set("query2", {"content": "2"})
        cache.set("query3", {"content": "3"})  # Should evict query1

        assert cache.get("query1") is None  # Evicted
        assert cache.get("query2") is not None
        assert cache.get("query3") is not None

    def test_lru_ordering(self):
        cache = ResponseCache(max_size=2)

        cache.set("query1", {"content": "1"})
        cache.set("query2", {"content": "2"})

        # Access query1 (moves to end)
        cache.get("query1")

        # Add query3 (should evict query2, not query1)
        cache.set("query3", {"content": "3"})

        assert cache.get("query1") is not None
        assert cache.get("query2") is None  # Evicted
        assert cache.get("query3") is not None

    def test_key_generation_with_model(self):
        cache = ResponseCache()
        response = {"content": "test"}

        cache.set("Test", response, model="gpt-4")

        # Different model = different key
        assert cache.get("Test", model="gpt-3.5") is None

        # Same model = same key
        assert cache.get("Test", model="gpt-4") is not None

    def test_key_generation_with_params(self):
        cache = ResponseCache()
        response = {"content": "test"}

        cache.set("Test", response, params={"temp": 0.7})

        # Different params = different key
        assert cache.get("Test", params={"temp": 0.9}) is None

        # Same params = same key
        assert cache.get("Test", params={"temp": 0.7}) is not None

    def test_clear(self):
        cache = ResponseCache()

        cache.set("query1", {"content": "1"})
        cache.set("query2", {"content": "2"})

        cache.clear()

        assert cache.get("query1") is None
        assert cache.get("query2") is None
        assert len(cache.cache) == 0

    def test_stats(self):
        cache = ResponseCache()

        cache.set("query1", {"content": "1"})
        cache.get("query1")  # Hit
        cache.get("query2")  # Miss

        stats = cache.get_stats()

        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["sets"] == 1
        assert stats["size"] == 1
        assert stats["hit_rate"] == 0.5

    def test_eviction_stats(self):
        cache = ResponseCache(max_size=2)

        cache.set("query1", {"content": "1"})
        cache.set("query2", {"content": "2"})
        cache.set("query3", {"content": "3"})  # Triggers eviction

        stats = cache.get_stats()
        assert stats["evictions"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
