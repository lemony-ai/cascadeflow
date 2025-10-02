"""Tests for utility functions."""

import pytest
from cascadeflow.utils import (
    format_cost,
    estimate_tokens,
    truncate_text,
    calculate_cosine_similarity,
    parse_model_identifier,
)


class TestFormatCost:
    """Tests for format_cost function."""

    def test_zero_cost(self):
        """Test formatting zero cost."""
        assert format_cost(0.0) == "$0.00"

    def test_small_cost(self):
        """Test formatting small cost."""
        assert format_cost(0.00425) == "$0.0043"
        assert format_cost(0.00001) == "$0.0000"

    def test_large_cost(self):
        """Test formatting larger cost."""
        assert format_cost(1.5) == "$1.50"
        assert format_cost(10.0) == "$10.00"


class TestEstimateTokens:
    """Tests for estimate_tokens function."""

    def test_short_text(self):
        """Test token estimation for short text."""
        tokens = estimate_tokens("Hello")
        assert tokens >= 1  # At least 1 token

    def test_longer_text(self):
        """Test token estimation for longer text."""
        text = "This is a longer sentence with multiple words."
        tokens = estimate_tokens(text)
        assert tokens > 5  # Should be multiple tokens

    def test_empty_text(self):
        """Test token estimation for empty text."""
        tokens = estimate_tokens("")
        assert tokens == 1  # Minimum 1 token


class TestTruncateText:
    """Tests for truncate_text function."""

    def test_short_text_no_truncate(self):
        """Test that short text is not truncated."""
        text = "Short"
        result = truncate_text(text, max_length=10)
        assert result == "Short"

    def test_long_text_truncate(self):
        """Test that long text is truncated."""
        text = "This is a very long text that should be truncated"
        result = truncate_text(text, max_length=10)
        assert result == "This is..."
        assert len(result) == 10

    def test_custom_suffix(self):
        """Test truncation with custom suffix."""
        text = "This is a very long text"
        result = truncate_text(text, max_length=10, suffix="→")
        assert result.endswith("→")


class TestCosineSimilarity:
    """Tests for calculate_cosine_similarity function."""

    def test_identical_vectors(self):
        """Test cosine similarity of identical vectors."""
        vec1 = [1, 0, 0]
        vec2 = [1, 0, 0]
        similarity = calculate_cosine_similarity(vec1, vec2)
        assert similarity == 1.0

    def test_orthogonal_vectors(self):
        """Test cosine similarity of orthogonal vectors."""
        vec1 = [1, 0, 0]
        vec2 = [0, 1, 0]
        similarity = calculate_cosine_similarity(vec1, vec2)
        assert similarity == 0.0

    def test_opposite_vectors(self):
        """Test cosine similarity of opposite vectors."""
        vec1 = [1, 0, 0]
        vec2 = [-1, 0, 0]
        similarity = calculate_cosine_similarity(vec1, vec2)
        assert 0.0 <= similarity <= 1.0  # Should be clamped to [0, 1]

    def test_zero_vector(self):
        """Test cosine similarity with zero vector."""
        vec1 = [0, 0, 0]
        vec2 = [1, 1, 1]
        similarity = calculate_cosine_similarity(vec1, vec2)
        assert similarity == 0.0


class TestParseModelIdentifier:
    """Tests for parse_model_identifier function."""

    def test_with_provider(self):
        """Test parsing identifier with provider."""
        provider, model = parse_model_identifier("openai:gpt-4")
        assert provider == "openai"
        assert model == "gpt-4"

    def test_without_provider(self):
        """Test parsing identifier without provider."""
        provider, model = parse_model_identifier("gpt-4")
        assert provider == ""
        assert model == "gpt-4"

    def test_multiple_colons(self):
        """Test parsing identifier with multiple colons."""
        provider, model = parse_model_identifier("openai:model:with:colons")
        assert provider == "openai"
        assert model == "model:with:colons"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])