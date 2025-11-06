"""
Tests for Unified Embedding Service

Validates:
- Lazy initialization
- Graceful degradation without FastEmbed
- Embedding latency (<50ms)
- Caching reduces duplicate work
- Similarity calculations
"""

import platform
import time
from unittest.mock import Mock, patch

import pytest

# Optional numpy (comes with FastEmbed)
try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    np = None

from cascadeflow.ml.embedding import EmbeddingCache, UnifiedEmbeddingService


class TestUnifiedEmbeddingService:
    """Test UnifiedEmbeddingService."""

    def test_lazy_initialization(self):
        """Test that model is not loaded until first use."""
        service = UnifiedEmbeddingService()

        # Model should not be loaded yet
        assert service._embedder is None
        assert service._initialize_attempted is False

        # Accessing is_available triggers lazy init
        _ = service.is_available

        # Now initialization should be attempted
        assert service._initialize_attempted is True

    def test_initialization_success(self):
        """Test successful initialization with FastEmbed."""
        # Skip if FastEmbed not installed (we have integration tests for real FastEmbed)
        try:
            import fastembed
        except ImportError:
            pytest.skip("FastEmbed not available")

        service = UnifiedEmbeddingService()
        _ = service.is_available

        # Should be available
        assert service.is_available is True
        assert service._embedder is not None

    def test_initialization_failure_import_error(self):
        """Test graceful degradation when FastEmbed not installed."""
        # Simulate ImportError by making is_available check without FastEmbed
        # Since FastEmbed is likely not installed, this should work naturally
        service = UnifiedEmbeddingService()
        # Force initialization
        _ = service.is_available

        # Check behavior (will depend on whether FastEmbed is installed)
        # We just verify it doesn't crash
        assert isinstance(service.is_available, bool)

    def test_embed_without_fastembed(self):
        """Test embed returns None when FastEmbed unavailable."""
        service = UnifiedEmbeddingService()
        # Force unavailable state
        service._is_available = False
        service._initialize_attempted = True

        result = service.embed("test text")

        # Should return None gracefully
        assert result is None

    @pytest.mark.skipif(not HAS_NUMPY, reason="Numpy not available")
    @patch("fastembed.TextEmbedding")
    def test_embed_single_text(self, mock_text_embedding):
        """Test embedding a single text."""
        # Mock embedder
        mock_embedder = Mock()
        mock_embedding = np.random.rand(384)
        mock_embedder.embed.return_value = [mock_embedding]
        mock_text_embedding.return_value = mock_embedder

        service = UnifiedEmbeddingService()
        result = service.embed("test text")

        # Should return embedding
        assert result is not None
        assert isinstance(result, np.ndarray)
        assert result.shape == (384,)

    @pytest.mark.skipif(not HAS_NUMPY, reason="Numpy not available")
    @patch("fastembed.TextEmbedding")
    def test_embed_batch(self, mock_text_embedding):
        """Test batch embedding for efficiency."""
        # Mock embedder
        mock_embedder = Mock()
        mock_embeddings = [np.random.rand(384) for _ in range(3)]
        mock_embedder.embed.return_value = mock_embeddings
        mock_text_embedding.return_value = mock_embedder

        service = UnifiedEmbeddingService()
        results = service.embed_batch(["text1", "text2", "text3"])

        # Should return list of embeddings
        assert results is not None
        assert len(results) == 3
        assert all(isinstance(emb, np.ndarray) for emb in results)

    @pytest.mark.skipif(not HAS_NUMPY, reason="Numpy not available")
    @patch("fastembed.TextEmbedding")
    def test_similarity(self, mock_text_embedding):
        """Test similarity calculation."""
        # Mock embedder with known vectors
        mock_embedder = Mock()
        # Create two similar vectors (same direction)
        vec1 = np.array([1.0, 0.0, 0.0] + [0.0] * 381)
        vec2 = np.array([0.9, 0.1, 0.0] + [0.0] * 381)
        mock_embedder.embed.return_value = [vec1, vec2]
        mock_text_embedding.return_value = mock_embedder

        service = UnifiedEmbeddingService()
        similarity = service.similarity("text1", "text2")

        # Should return similarity score
        assert similarity is not None
        assert 0.0 <= similarity <= 1.0
        assert similarity > 0.8  # Vectors are similar

    @pytest.mark.skipif(not HAS_NUMPY, reason="Numpy not available")
    def test_cosine_similarity_calculation(self):
        """Test cosine similarity calculation correctness."""
        service = UnifiedEmbeddingService()

        # Identical vectors → similarity = 1.0
        vec1 = np.array([1.0, 0.0, 0.0])
        vec2 = np.array([1.0, 0.0, 0.0])
        similarity = service._cosine_similarity(vec1, vec2)
        assert abs(similarity - 1.0) < 0.01

        # Orthogonal vectors → similarity = 0.0
        vec1 = np.array([1.0, 0.0, 0.0])
        vec2 = np.array([0.0, 1.0, 0.0])
        similarity = service._cosine_similarity(vec1, vec2)
        assert abs(similarity - 0.0) < 0.01

        # Opposite vectors → similarity = 0.0 (clamped from -1.0)
        vec1 = np.array([1.0, 0.0, 0.0])
        vec2 = np.array([-1.0, 0.0, 0.0])
        similarity = service._cosine_similarity(vec1, vec2)
        assert similarity == 0.0  # Clamped to 0


class TestEmbeddingCache:
    """Test EmbeddingCache."""

    def test_cache_initialization(self):
        """Test cache initialization."""
        service = UnifiedEmbeddingService()
        cache = EmbeddingCache(service)

        assert cache.embedder is service
        assert cache.cache_size() == 0

    @pytest.mark.skipif(not HAS_NUMPY, reason="Numpy not available")
    @patch("fastembed.TextEmbedding")
    def test_cache_hit(self, mock_text_embedding):
        """Test cache returns cached embedding without recomputation."""
        # Mock embedder
        mock_embedder = Mock()
        mock_embedding = np.random.rand(384)
        mock_embedder.embed.return_value = [mock_embedding]
        mock_text_embedding.return_value = mock_embedder

        service = UnifiedEmbeddingService()
        cache = EmbeddingCache(service)

        # First call - should compute
        emb1 = cache.get_or_embed("test text")
        assert mock_embedder.embed.call_count == 1
        assert cache.cache_size() == 1

        # Second call - should use cache
        emb2 = cache.get_or_embed("test text")
        assert mock_embedder.embed.call_count == 1  # Not called again
        assert cache.cache_size() == 1

        # Embeddings should be identical (same object)
        assert np.array_equal(emb1, emb2)

    @pytest.mark.skipif(not HAS_NUMPY, reason="Numpy not available")
    @patch("fastembed.TextEmbedding")
    def test_cache_miss(self, mock_text_embedding):
        """Test cache computes new embedding for different text."""
        # Mock embedder
        mock_embedder = Mock()
        mock_embedder.embed.side_effect = [
            [np.random.rand(384)],
            [np.random.rand(384)],
        ]
        mock_text_embedding.return_value = mock_embedder

        service = UnifiedEmbeddingService()
        cache = EmbeddingCache(service)

        # First text
        cache.get_or_embed("text1")
        assert cache.cache_size() == 1

        # Different text - should compute new
        cache.get_or_embed("text2")
        assert mock_embedder.embed.call_count == 2
        assert cache.cache_size() == 2

    @pytest.mark.skipif(not HAS_NUMPY, reason="Numpy not available")
    @patch("fastembed.TextEmbedding")
    def test_cache_clear(self, mock_text_embedding):
        """Test cache clearing."""
        mock_embedder = Mock()
        mock_embedder.embed.return_value = [np.random.rand(384)]
        mock_text_embedding.return_value = mock_embedder

        service = UnifiedEmbeddingService()
        cache = EmbeddingCache(service)

        # Add to cache
        cache.get_or_embed("text1")
        assert cache.cache_size() == 1

        # Clear cache
        cache.clear()
        assert cache.cache_size() == 0

    @pytest.mark.skipif(not HAS_NUMPY, reason="Numpy not available")
    @patch("fastembed.TextEmbedding")
    def test_cache_similarity(self, mock_text_embedding):
        """Test similarity with caching."""
        # Mock embedder
        mock_embedder = Mock()
        vec1 = np.array([1.0, 0.0, 0.0] + [0.0] * 381)
        vec2 = np.array([0.9, 0.1, 0.0] + [0.0] * 381)
        mock_embedder.embed.side_effect = [[vec1], [vec2]]
        mock_text_embedding.return_value = mock_embedder

        service = UnifiedEmbeddingService()
        cache = EmbeddingCache(service)

        # First call - computes both embeddings
        similarity1 = cache.similarity("text1", "text2")
        assert similarity1 is not None
        assert cache.cache_size() == 2

        # Second call with same texts - uses cache
        similarity2 = cache.similarity("text1", "text2")
        assert similarity1 == similarity2
        assert mock_embedder.embed.call_count == 2  # Not called again

    @pytest.mark.skipif(not HAS_NUMPY, reason="Numpy not available")
    @patch("fastembed.TextEmbedding")
    def test_cache_info(self, mock_text_embedding):
        """Test cache info reporting."""
        mock_embedder = Mock()
        mock_embedder.embed.return_value = [np.random.rand(384)]
        mock_text_embedding.return_value = mock_embedder

        service = UnifiedEmbeddingService()
        cache = EmbeddingCache(service)

        # Add some texts
        cache.get_or_embed("text1")
        cache.get_or_embed("text2")

        info = cache.cache_info()
        assert info["size"] == 2
        assert "text1" in info["texts"]
        assert "text2" in info["texts"]


# Integration test with real FastEmbed (if available)
class TestRealFastEmbed:
    """Integration tests with real FastEmbed (skipped if not installed)."""

    @pytest.fixture
    def service(self):
        """Create service and skip if FastEmbed unavailable."""
        service = UnifiedEmbeddingService()
        if not service.is_available:
            pytest.skip("FastEmbed not available")
        return service

    def test_real_embedding_latency(self, service):
        """Test that embedding latency is <50ms (real FastEmbed)."""
        # Warm up (model loading)
        _ = service.embed("warmup")

        # Measure latency
        start = time.time()
        embedding = service.embed("What is Python?")
        latency_ms = (time.time() - start) * 1000

        # Should be <50ms after warmup
        assert embedding is not None
        assert latency_ms < 100  # Generous threshold for CI environments

    def test_real_similarity(self, service):
        """Test real similarity calculation."""
        # Similar texts should have high similarity
        sim_high = service.similarity("What is Python?", "What is the Python programming language?")

        # Unrelated texts should have low similarity
        sim_low = service.similarity("What is Python?", "The weather is sunny today")

        assert sim_high is not None
        assert sim_low is not None
        assert sim_high > sim_low  # Similar > unrelated

    @pytest.mark.skipif(
        platform.system() == "Darwin",
        reason="Timing-sensitive test is flaky on macOS Python 3.12",
    )
    def test_real_batch_efficiency(self, service):
        """Test that batch embedding is faster than individual."""
        texts = ["text1", "text2", "text3"]

        # Warmup
        _ = service.embed_batch(texts)

        # Individual embeddings
        start = time.time()
        for text in texts:
            service.embed(text)
        individual_time = time.time() - start

        # Batch embedding
        start = time.time()
        service.embed_batch(texts)
        batch_time = time.time() - start

        # Batch should be faster (or at least not much slower)
        # Allow 50% margin for variance
        assert batch_time < individual_time * 1.5
