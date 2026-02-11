"""
Response caching system.

Provides:
- In-memory LRU cache
- Cache key generation
- TTL support
- Cache statistics
- Optional semantic deduplication via FastEmbed (v2)
"""

import hashlib
import logging
import time
from collections import OrderedDict
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Threshold for semantic cache hit (cosine similarity >= 0.95 = near-identical query)
SEMANTIC_SIMILARITY_THRESHOLD = 0.95


class ResponseCache:
    """
    In-memory LRU cache for responses with optional semantic deduplication.

    When ``enable_semantic_dedup=True`` and FastEmbed is available, cache misses
    trigger a cosine-similarity scan against recent query embeddings. Queries
    with similarity >= 0.95 are treated as cache hits, avoiding a redundant LLM
    call for paraphrased questions (e.g. "What is Python?" vs "Tell me about Python").

    Example:
        >>> cache = ResponseCache(max_size=1000, default_ttl=3600, enable_semantic_dedup=True)
        >>>
        >>> cache.set("What is Python?", response_data)
        >>> # Exact match
        >>> cache.get("What is Python?")  # hit
        >>> # Semantic match (paraphrase)
        >>> cache.get("Tell me about Python")  # also hit (cosine >= 0.95)
    """

    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: int = 3600,
        enable_semantic_dedup: bool = False,
    ):
        """
        Initialize cache.

        Args:
            max_size: Maximum number of cached items
            default_ttl: Default TTL in seconds
            enable_semantic_dedup: Enable semantic deduplication using FastEmbed.
                When True, cache misses will try cosine-similarity matching
                against recent queries (~25ms overhead on miss only).
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.enable_semantic_dedup = enable_semantic_dedup
        self.cache: OrderedDict = OrderedDict()
        self.stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "evictions": 0,
            "semantic_hits": 0,
        }

        # Semantic dedup state (lazy-initialized)
        self._embedder = None
        self._embedder_checked = False
        # Map cache key -> (query_text, embedding_vector)
        self._query_embeddings: dict[str, tuple[str, Any]] = {}

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

        Returns None if not found or expired. When semantic dedup is enabled,
        a hash miss triggers a cosine-similarity scan (~25ms) to find
        paraphrased queries with the same intent.
        """
        key = self._generate_key(query, model, params)

        if key in self.cache:
            entry = self.cache[key]
            if time.time() > entry["expires_at"]:
                del self.cache[key]
                self._query_embeddings.pop(key, None)
                self.stats["misses"] += 1
                return None
            self.cache.move_to_end(key)
            self.stats["hits"] += 1
            logger.debug(f"Cache hit for query: {query[:50]}...")
            return entry["response"]

        # Hash miss -- try semantic dedup if enabled
        if self.enable_semantic_dedup and self._query_embeddings:
            result = self._semantic_lookup(query)
            if result is not None:
                self.stats["semantic_hits"] += 1
                self.stats["hits"] += 1
                logger.debug(f"Semantic cache hit for query: {query[:50]}...")
                return result

        self.stats["misses"] += 1
        return None

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
            evicted_key, _ = self.cache.popitem(last=False)
            self._query_embeddings.pop(evicted_key, None)
            self.stats["evictions"] += 1

        # Add entry
        self.cache[key] = {
            "response": response,
            "created_at": time.time(),
            "expires_at": time.time() + (ttl or self.default_ttl),
        }
        self.stats["sets"] += 1

        # Store embedding for semantic dedup (best-effort, non-blocking)
        if self.enable_semantic_dedup:
            self._store_embedding(key, query)

        logger.debug(f"Cached response for query: {query[:50]}...")

    def clear(self):
        """Clear all cache."""
        self.cache.clear()
        self._query_embeddings.clear()
        logger.info("Cache cleared")

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        total_lookups = self.stats["hits"] + self.stats["misses"]
        hit_rate = self.stats["hits"] / total_lookups if total_lookups > 0 else 0

        return {
            **self.stats,
            "size": len(self.cache),
            "max_size": self.max_size,
            "hit_rate": hit_rate,
            "semantic_dedup_enabled": self.enable_semantic_dedup,
            "embeddings_cached": len(self._query_embeddings),
        }

    # ------------------------------------------------------------------
    # Semantic dedup internals
    # ------------------------------------------------------------------

    def _get_embedder(self):
        """Lazy-initialize the embedding service."""
        if self._embedder_checked:
            return self._embedder
        self._embedder_checked = True
        try:
            from cascadeflow.ml.embedding import UnifiedEmbeddingService

            svc = UnifiedEmbeddingService()
            if svc.is_available:
                self._embedder = svc
        except Exception:
            pass
        return self._embedder

    def _store_embedding(self, key: str, query: str):
        """Embed and store query for future semantic lookups."""
        embedder = self._get_embedder()
        if embedder is None:
            return
        try:
            vec = embedder.embed(query)
            if vec is not None:
                self._query_embeddings[key] = (query, vec)
        except Exception:
            pass

    def _semantic_lookup(self, query: str) -> Optional[dict[str, Any]]:
        """Find a cached entry whose query is semantically identical (cosine >= 0.95)."""
        embedder = self._get_embedder()
        if embedder is None:
            return None
        try:
            query_vec = embedder.embed(query)
            if query_vec is None:
                return None
        except Exception:
            return None

        best_key = None
        best_sim = 0.0
        now = time.time()

        for cached_key, (_, cached_vec) in self._query_embeddings.items():
            # Skip expired entries
            entry = self.cache.get(cached_key)
            if entry is None or now > entry["expires_at"]:
                continue
            sim = embedder._cosine_similarity(query_vec, cached_vec)
            if sim > best_sim:
                best_sim = sim
                best_key = cached_key

        if best_sim >= SEMANTIC_SIMILARITY_THRESHOLD and best_key is not None:
            entry = self.cache[best_key]
            self.cache.move_to_end(best_key)
            return entry["response"]

        return None
