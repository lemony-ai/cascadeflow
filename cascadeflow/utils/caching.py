"""
Response caching system.

Provides:
- In-memory LRU cache
- Cache key generation
- TTL support
- Cache statistics
"""

import hashlib
import logging
import time
from collections import OrderedDict
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ResponseCache:
    """
    Simple in-memory LRU cache for responses.

    Example:
        >>> cache = ResponseCache(max_size=1000, default_ttl=3600)
        >>>
        >>> # Store response
        >>> cache.set("What is 2+2?", response_data, ttl=600)
        >>>
        >>> # Retrieve response
        >>> cached = cache.get("What is 2+2?")
        >>> if cached:
        ...     print("Cache hit!")
    """

    def __init__(self, max_size: int = 1000, default_ttl: int = 3600):
        """
        Initialize cache.

        Args:
            max_size: Maximum number of cached items
            default_ttl: Default TTL in seconds
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cache: OrderedDict = OrderedDict()
        self.stats = {"hits": 0, "misses": 0, "sets": 0, "evictions": 0}

    def _generate_key(
        self, query: str, model: Optional[str] = None, params: Optional[dict[str, Any]] = None
    ) -> str:
        """Generate cache key from query and parameters."""
        key_data = {"query": query, "model": model, "params": params or {}}
        key_str = str(sorted(key_data.items()))
        return hashlib.sha256(key_str.encode()).hexdigest()

    def get(
        self, query: str, model: Optional[str] = None, params: Optional[dict[str, Any]] = None
    ) -> Optional[dict[str, Any]]:
        """
        Get cached response.

        Returns None if not found or expired.
        """
        key = self._generate_key(query, model, params)

        if key not in self.cache:
            self.stats["misses"] += 1
            return None

        # Check TTL
        entry = self.cache[key]
        if time.time() > entry["expires_at"]:
            # Expired
            del self.cache[key]
            self.stats["misses"] += 1
            return None

        # Move to end (LRU)
        self.cache.move_to_end(key)
        self.stats["hits"] += 1

        logger.debug(f"Cache hit for query: {query[:50]}...")
        return entry["response"]

    def set(
        self,
        query: str,
        response: dict[str, Any],
        model: Optional[str] = None,
        params: Optional[dict[str, Any]] = None,
        ttl: Optional[int] = None,
    ):
        """Set cache entry."""
        key = self._generate_key(query, model, params)

        # Evict if full
        if len(self.cache) >= self.max_size:
            # Remove oldest (first item)
            self.cache.popitem(last=False)
            self.stats["evictions"] += 1

        # Add entry
        self.cache[key] = {
            "response": response,
            "created_at": time.time(),
            "expires_at": time.time() + (ttl or self.default_ttl),
        }
        self.stats["sets"] += 1

        logger.debug(f"Cached response for query: {query[:50]}...")

    def clear(self):
        """Clear all cache."""
        self.cache.clear()
        logger.info("Cache cleared")

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        hit_rate = (
            self.stats["hits"] / (self.stats["hits"] + self.stats["misses"])
            if self.stats["hits"] + self.stats["misses"] > 0
            else 0
        )

        return {
            **self.stats,
            "size": len(self.cache),
            "max_size": self.max_size,
            "hit_rate": hit_rate,
        }
