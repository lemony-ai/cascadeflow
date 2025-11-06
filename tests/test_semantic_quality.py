"""
Tests for Optional Semantic ML Quality Validation (Phase 3.1)

This module tests the semantic quality checking functionality including:
- Semantic similarity checking
- Toxicity detection
- Graceful degradation without FastEmbed
- Combined validation
- Edge cases
"""

import sys
from unittest.mock import MagicMock, patch

import pytest

# Import the module
from cascadeflow.quality.semantic import (
    SemanticQualityChecker,
    SemanticQualityResult,
    check_semantic_quality,
)

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def mock_fastembed_available():
    """Mock FastEmbed as available."""
    # Mock the fastembed module at import time
    mock_fastembed = MagicMock()
    mock_model = MagicMock()
    mock_model.embed.side_effect = lambda texts: [
        [0.1] * 384 for _ in texts  # BGE-small is 384-dim
    ]
    mock_fastembed.TextEmbedding.return_value = mock_model

    with patch.dict("sys.modules", {"fastembed": mock_fastembed}):
        yield mock_fastembed


@pytest.fixture
def mock_fastembed_unavailable():
    """Mock FastEmbed as unavailable."""
    # Remove fastembed from sys.modules if it exists
    if "fastembed" in sys.modules:
        del sys.modules["fastembed"]
    # Make import fail
    with patch.dict("sys.modules", {"fastembed": None}):
        yield


# ============================================================================
# INITIALIZATION TESTS
# ============================================================================


def test_semantic_checker_init_with_fastembed(mock_fastembed_available):
    """Test initialization when FastEmbed is available."""
    checker = SemanticQualityChecker()

    assert checker.is_available()
    assert checker.model is not None
    assert checker.similarity_threshold == 0.5
    assert checker.toxicity_threshold == 0.7


def test_semantic_checker_init_without_fastembed(mock_fastembed_unavailable):
    """Test graceful degradation when FastEmbed is not available."""
    checker = SemanticQualityChecker()

    assert not checker.is_available()
    # checker.model is now an UnifiedEmbeddingService instance, check embedder instead
    assert checker.embedder is not None  # Service exists
    assert not checker.embedder.is_available  # But FastEmbed not available


def test_semantic_checker_custom_thresholds(mock_fastembed_available):
    """Test initialization with custom thresholds."""
    checker = SemanticQualityChecker(
        similarity_threshold=0.7,
        toxicity_threshold=0.5,
    )

    assert checker.similarity_threshold == 0.7
    assert checker.toxicity_threshold == 0.5


# ============================================================================
# SEMANTIC SIMILARITY TESTS
# ============================================================================


def test_check_similarity_high(mock_fastembed_available):
    """Test high semantic similarity between related texts."""
    import numpy as np

    checker = SemanticQualityChecker()

    # Mock identical embeddings (perfect similarity)
    # Mock at embedder level, returning numpy arrays
    checker.embedder.embed = lambda text: np.array([0.5, 0.5, 0.5])

    similarity = checker.check_similarity(
        query="What is machine learning?",
        response="Machine learning is a subset of AI that enables computers to learn.",
    )

    # Identical embeddings should have similarity 1.0
    assert similarity == pytest.approx(1.0, abs=0.01)


def test_check_similarity_low(mock_fastembed_available):
    """Test low semantic similarity between unrelated texts."""
    import numpy as np

    checker = SemanticQualityChecker()

    # Mock orthogonal embeddings (zero similarity)
    # Track call count to return different embeddings
    call_count = [0]

    def mock_embed(text):
        call_count[0] += 1
        if call_count[0] == 1:
            return np.array([1.0, 0.0, 0.0])  # Query embedding
        else:
            return np.array([0.0, 1.0, 0.0])  # Response embedding (orthogonal)

    checker.embedder.embed = mock_embed

    similarity = checker.check_similarity(
        query="What is machine learning?", response="The weather is sunny today."
    )

    # Orthogonal embeddings should have similarity ~0.0
    assert similarity == pytest.approx(0.0, abs=0.1)


def test_check_similarity_unavailable(mock_fastembed_unavailable):
    """Test similarity check raises error when FastEmbed unavailable."""
    checker = SemanticQualityChecker()

    with pytest.raises(RuntimeError, match="Semantic checking not available"):
        checker.check_similarity("query", "response")


def test_check_similarity_empty_strings(mock_fastembed_available):
    """Test similarity check with empty strings."""
    import numpy as np

    checker = SemanticQualityChecker()

    # Mock zero embeddings
    checker.embedder.embed = lambda text: np.array([0.0, 0.0, 0.0])

    similarity = checker.check_similarity("", "")

    # Zero embeddings should return 0.0 (handled by _cosine_similarity)
    assert similarity == 0.0


# ============================================================================
# TOXICITY DETECTION TESTS
# ============================================================================


def test_check_toxicity_clean(mock_fastembed_available):
    """Test toxicity check on clean text."""
    checker = SemanticQualityChecker()

    is_toxic, score = checker.check_toxicity(
        "This is a helpful and informative response about machine learning."
    )

    assert not is_toxic
    assert score == 0.0


def test_check_toxicity_single_keyword(mock_fastembed_available):
    """Test toxicity check with single toxic keyword."""
    checker = SemanticQualityChecker()

    is_toxic, score = checker.check_toxicity("I hate this implementation.")

    # Should detect "hate" keyword
    assert score > 0.0
    # With default threshold 0.7, single keyword (0.3) should not be toxic
    assert not is_toxic


def test_check_toxicity_multiple_keywords(mock_fastembed_available):
    """Test toxicity check with multiple toxic keywords."""
    checker = SemanticQualityChecker()

    is_toxic, score = checker.check_toxicity(
        "This violent and racist hate speech should be flagged."
    )

    # Should detect multiple keywords
    assert score > 0.5
    assert is_toxic  # Should exceed default threshold


def test_check_toxicity_custom_threshold(mock_fastembed_available):
    """Test toxicity check with custom threshold."""
    checker = SemanticQualityChecker(toxicity_threshold=0.2)

    is_toxic, score = checker.check_toxicity("I hate this.")

    # With lower threshold (0.2), single keyword (0.3) should be toxic
    assert is_toxic


def test_check_toxicity_unavailable(mock_fastembed_unavailable):
    """Test toxicity check raises error when unavailable."""
    checker = SemanticQualityChecker()

    with pytest.raises(RuntimeError, match="Semantic checking not available"):
        checker.check_toxicity("text")


# ============================================================================
# COMBINED VALIDATION TESTS
# ============================================================================


def test_validate_pass(mock_fastembed_available):
    """Test validation passes with high similarity and no toxicity."""
    import numpy as np

    checker = SemanticQualityChecker(similarity_threshold=0.5)

    # Mock high similarity embeddings
    checker.embedder.embed = lambda text: np.array([0.5, 0.5, 0.5])

    result = checker.validate(
        query="What is Python?", response="Python is a high-level programming language."
    )

    assert result.passed
    assert result.similarity >= 0.5
    assert not result.is_toxic
    assert result.reason is None


def test_validate_fail_low_similarity(mock_fastembed_available):
    """Test validation fails due to low similarity."""
    import numpy as np

    checker = SemanticQualityChecker(similarity_threshold=0.8)

    # Mock medium similarity embeddings - use different vectors for query/response
    call_count = [0]

    def mock_embed(text):
        call_count[0] += 1
        if call_count[0] == 1:
            return np.array([1.0, 0.5, 0.0])  # Query
        else:
            return np.array([0.5, 1.0, 0.0])  # Response (different)

    checker.embedder.embed = mock_embed

    result = checker.validate(query="What is AI?", response="The weather is nice.")

    assert not result.passed
    assert result.similarity < 0.8
    assert "low_similarity" in result.reason


def test_validate_fail_toxic(mock_fastembed_available):
    """Test validation fails due to toxic content."""
    import numpy as np

    checker = SemanticQualityChecker(similarity_threshold=0.5)

    # Mock high similarity embeddings
    checker.embedder.embed = lambda text: np.array([0.5, 0.5, 0.5])

    result = checker.validate(
        query="Explain the concept.",
        response="This violent and hateful racist content is inappropriate.",
        check_toxicity=True,
    )

    assert not result.passed
    assert result.is_toxic
    assert "toxic_content" in result.reason


def test_validate_skip_toxicity(mock_fastembed_available):
    """Test validation can skip toxicity check."""
    import numpy as np

    checker = SemanticQualityChecker()

    # Mock high similarity embeddings
    checker.embedder.embed = lambda text: np.array([0.5, 0.5, 0.5])

    result = checker.validate(
        query="Query", response="Response with hate keyword", check_toxicity=False
    )

    # Should pass because toxicity check was skipped
    assert result.passed
    assert not result.is_toxic
    assert result.toxicity_score == 0.0


def test_validate_unavailable(mock_fastembed_unavailable):
    """Test validation returns error result when unavailable."""
    checker = SemanticQualityChecker()

    result = checker.validate("query", "response")

    assert not result.passed
    assert result.similarity == 0.0
    assert result.reason == "semantic_checking_unavailable"
    assert result.metadata["available"] is False


def test_validate_metadata(mock_fastembed_available):
    """Test validation includes proper metadata."""
    import numpy as np

    checker = SemanticQualityChecker(
        model_name="BAAI/bge-small-en-v1.5",
        similarity_threshold=0.6,
        toxicity_threshold=0.8,
    )

    # Mock high similarity embeddings
    checker.embedder.embed = lambda text: np.array([0.5, 0.5, 0.5])

    result = checker.validate("query", "response")

    assert result.metadata["model"] == "BAAI/bge-small-en-v1.5"
    assert result.metadata["similarity_threshold"] == 0.6
    assert result.metadata["toxicity_threshold"] == 0.8


# ============================================================================
# CONVENIENCE FUNCTION TESTS
# ============================================================================


def test_check_semantic_quality_convenience(mock_fastembed_available):
    """Test convenience function for one-off checks."""
    # Mock high similarity embeddings
    with patch("cascadeflow.quality.semantic.SemanticQualityChecker") as mock_checker:
        mock_instance = MagicMock()
        mock_instance.is_available.return_value = True
        mock_instance.validate.return_value = SemanticQualityResult(
            similarity=0.9,
            is_toxic=False,
            toxicity_score=0.0,
            passed=True,
        )
        mock_checker.return_value = mock_instance

        result = check_semantic_quality(
            query="What is AI?", response="AI is artificial intelligence."
        )

        assert result is not None
        assert result.passed
        assert result.similarity == 0.9


def test_check_semantic_quality_unavailable(mock_fastembed_unavailable):
    """Test convenience function returns None when unavailable."""
    result = check_semantic_quality("query", "response")

    assert result is None


# ============================================================================
# EDGE CASES
# ============================================================================


def test_cosine_similarity_zero_vectors(mock_fastembed_available):
    """Test cosine similarity handles zero vectors."""
    import numpy as np

    from cascadeflow.ml.embedding import UnifiedEmbeddingService

    # Test the static method directly
    similarity = UnifiedEmbeddingService._cosine_similarity(
        np.array([0, 0, 0]), np.array([0, 0, 0])
    )

    assert similarity == 0.0


def test_cosine_similarity_one_zero_vector(mock_fastembed_available):
    """Test cosine similarity handles one zero vector."""
    import numpy as np

    from cascadeflow.ml.embedding import UnifiedEmbeddingService

    # Test the static method directly
    similarity = UnifiedEmbeddingService._cosine_similarity(
        np.array([1, 1, 1]), np.array([0, 0, 0])
    )

    assert similarity == 0.0


def test_very_long_text(mock_fastembed_available):
    """Test semantic checking handles very long texts."""
    import numpy as np

    checker = SemanticQualityChecker()

    # Mock embeddings
    checker.embedder.embed = lambda text: np.array([0.5, 0.5, 0.5])

    long_text = "This is a very long text. " * 1000  # ~5000 words

    result = checker.validate(query="Summarize this document", response=long_text)

    # Should not crash, should return valid result
    assert isinstance(result, SemanticQualityResult)


def test_unicode_text(mock_fastembed_available):
    """Test semantic checking handles unicode text."""
    import numpy as np

    checker = SemanticQualityChecker()

    # Mock embeddings
    checker.embedder.embed = lambda text: np.array([0.5, 0.5, 0.5])

    result = checker.validate(
        query="Qu'est-ce que l'IA?", response="L'IA est l'intelligence artificielle. 🤖"
    )

    assert isinstance(result, SemanticQualityResult)
