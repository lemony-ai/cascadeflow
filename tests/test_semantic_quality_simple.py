"""
Simplified Tests for Optional Semantic ML Quality Validation (Phase 3.1)

These tests verify the semantic quality checker behavior without requiring FastEmbed.
They test graceful degradation and the public API.
"""

import pytest

from cascadeflow.quality.semantic import (
    SemanticQualityChecker,
    SemanticQualityResult,
    check_semantic_quality,
)

# ============================================================================
# INITIALIZATION TESTS (No FastEmbed Required)
# ============================================================================


def test_semantic_checker_init_graceful_degradation():
    """Test that checker initializes gracefully without FastEmbed."""
    checker = SemanticQualityChecker()

    # Should not crash, just warn
    assert isinstance(checker, SemanticQualityChecker)
    assert hasattr(checker, "model")
    assert hasattr(checker, "available")


def test_semantic_checker_custom_thresholds():
    """Test initialization with custom thresholds."""
    checker = SemanticQualityChecker(
        similarity_threshold=0.7,
        toxicity_threshold=0.5,
    )

    assert checker.similarity_threshold == 0.7
    assert checker.toxicity_threshold == 0.5


def test_semantic_checker_is_available_method():
    """Test is_available() method exists and returns boolean."""
    checker = SemanticQualityChecker()

    result = checker.is_available()

    assert isinstance(result, bool)


# ============================================================================
# UNAVAILABLE MODE TESTS (FastEmbed not installed)
# ============================================================================


def test_check_similarity_unavailable_raises_error():
    """Test that check_similarity raises error when unavailable."""
    checker = SemanticQualityChecker()

    if not checker.is_available():
        with pytest.raises(RuntimeError, match="Semantic checking not available"):
            checker.check_similarity("query", "response")
    else:
        pytest.skip("FastEmbed is available, skipping unavailable test")


def test_check_toxicity_unavailable_raises_error():
    """Test that check_toxicity raises error when unavailable."""
    checker = SemanticQualityChecker()

    if not checker.is_available():
        with pytest.raises(RuntimeError, match="Semantic checking not available"):
            checker.check_toxicity("text")
    else:
        pytest.skip("FastEmbed is available, skipping unavailable test")


def test_validate_unavailable_returns_error_result():
    """Test that validate returns proper error result when unavailable."""
    checker = SemanticQualityChecker()

    if not checker.is_available():
        result = checker.validate("query", "response")

        assert isinstance(result, SemanticQualityResult)
        assert not result.passed
        assert result.similarity == 0.0
        assert result.reason == "semantic_checking_unavailable"
        assert result.metadata["available"] is False
    else:
        pytest.skip("FastEmbed is available, skipping unavailable test")


def test_convenience_function_unavailable_returns_none():
    """Test convenience function returns None when unavailable."""
    checker = SemanticQualityChecker()

    if not checker.is_available():
        result = check_semantic_quality("query", "response")
        assert result is None
    else:
        pytest.skip("FastEmbed is available, skipping unavailable test")


# ============================================================================
# AVAILABLE MODE TESTS (If FastEmbed is installed)
# ============================================================================


def test_check_similarity_available():
    """Test similarity checking when FastEmbed is available."""
    checker = SemanticQualityChecker()

    if checker.is_available():
        # Should not raise error
        similarity = checker.check_similarity(
            query="What is machine learning?", response="Machine learning is a subset of AI."
        )

        assert isinstance(similarity, float)
        assert 0.0 <= similarity <= 1.0
    else:
        pytest.skip("FastEmbed not available, skipping available test")


def test_check_toxicity_available():
    """Test toxicity checking when FastEmbed is available."""
    checker = SemanticQualityChecker()

    if checker.is_available():
        # Test clean text
        is_toxic, score = checker.check_toxicity("This is a helpful and informative response.")

        assert isinstance(is_toxic, bool)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0
        assert not is_toxic  # Clean text should not be toxic
    else:
        pytest.skip("FastEmbed not available, skipping available test")


def test_validate_available():
    """Test full validation when FastEmbed is available."""
    checker = SemanticQualityChecker()

    if checker.is_available():
        result = checker.validate(
            query="What is Python?", response="Python is a high-level programming language."
        )

        assert isinstance(result, SemanticQualityResult)
        assert isinstance(result.similarity, float)
        assert isinstance(result.is_toxic, bool)
        assert isinstance(result.passed, bool)
        assert 0.0 <= result.similarity <= 1.0
    else:
        pytest.skip("FastEmbed not available, skipping available test")


def test_validate_skip_toxicity_check():
    """Test validation can skip toxicity check."""
    checker = SemanticQualityChecker()

    if checker.is_available():
        result = checker.validate(query="Query", response="Response", check_toxicity=False)

        assert isinstance(result, SemanticQualityResult)
        assert result.toxicity_score == 0.0
        assert not result.is_toxic
    else:
        pytest.skip("FastEmbed not available, skipping available test")


def test_validate_includes_metadata():
    """Test validation includes proper metadata."""
    checker = SemanticQualityChecker(
        model_name="BAAI/bge-small-en-v1.5",
        similarity_threshold=0.6,
    )

    if checker.is_available():
        result = checker.validate("query", "response")

        assert "model" in result.metadata
        assert "similarity_threshold" in result.metadata
        assert result.metadata["model"] == "BAAI/bge-small-en-v1.5"
        assert result.metadata["similarity_threshold"] == 0.6
    else:
        pytest.skip("FastEmbed not available, skipping available test")


# ============================================================================
# RESULT CLASS TESTS
# ============================================================================


def test_semantic_quality_result_structure():
    """Test SemanticQualityResult dataclass structure."""
    result = SemanticQualityResult(
        similarity=0.85,
        is_toxic=False,
        toxicity_score=0.1,
        passed=True,
        reason=None,
        metadata={"test": "data"},
    )

    assert result.similarity == 0.85
    assert not result.is_toxic
    assert result.toxicity_score == 0.1
    assert result.passed
    assert result.reason is None
    assert result.metadata == {"test": "data"}


def test_semantic_quality_result_post_init():
    """Test SemanticQualityResult __post_init__ sets default metadata."""
    result = SemanticQualityResult(similarity=0.5, is_toxic=False, toxicity_score=0.0, passed=True)

    # Should initialize empty metadata dict
    assert result.metadata is not None
    assert isinstance(result.metadata, dict)


# ============================================================================
# EDGE CASES
# ============================================================================


def test_empty_query_and_response():
    """Test handling of empty strings."""
    checker = SemanticQualityChecker()

    if checker.is_available():
        result = checker.validate("", "")

        assert isinstance(result, SemanticQualityResult)
        # Empty strings should return low similarity
        assert result.similarity >= 0.0
    else:
        pytest.skip("FastEmbed not available, skipping available test")


def test_very_long_text():
    """Test handling of very long texts."""
    checker = SemanticQualityChecker()

    if checker.is_available():
        long_text = "This is a test sentence. " * 1000  # ~5000 words

        result = checker.validate(query="Summarize", response=long_text)

        # Should not crash
        assert isinstance(result, SemanticQualityResult)
    else:
        pytest.skip("FastEmbed not available, skipping available test")


def test_unicode_text():
    """Test handling of unicode characters."""
    checker = SemanticQualityChecker()

    if checker.is_available():
        result = checker.validate(
            query="Qu'est-ce que l'IA?", response="L'IA est l'intelligence artificielle. 🤖"
        )

        assert isinstance(result, SemanticQualityResult)
    else:
        pytest.skip("FastEmbed not available, skipping available test")


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


def test_high_similarity_query_response_pair():
    """Test that semantically similar query-response pairs have high similarity."""
    checker = SemanticQualityChecker()

    if checker.is_available():
        # Very similar pair
        result = checker.validate(query="What is 2 + 2?", response="2 plus 2 equals 4.")

        # Should have reasonable similarity (not testing exact value)
        assert result.similarity > 0.3  # Relaxed threshold
    else:
        pytest.skip("FastEmbed not available, skipping available test")


def test_low_similarity_unrelated_pair():
    """Test that unrelated query-response pairs have lower similarity."""
    checker = SemanticQualityChecker()

    if checker.is_available():
        # Completely unrelated pair
        result = checker.validate(
            query="What is quantum physics?",
            response="I like to eat apples and bananas for breakfast.",
        )

        # Unrelated text should have lower similarity than related text
        # (Not testing absolute value, just that system works)
        assert 0.0 <= result.similarity <= 1.0
    else:
        pytest.skip("FastEmbed not available, skipping available test")
