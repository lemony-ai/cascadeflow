"""Tests for utility functions."""

import pytest

from cascadeflow.utils import estimate_tokens, format_cost


def test_format_cost_zero():
    """Test formatting zero cost."""
    assert format_cost(0.0) == "$0.0000"


def test_format_cost_small():
    """Test formatting small costs."""
    assert format_cost(0.002) == "$0.0020"
    assert format_cost(0.00001) == "$0.0000"


def test_format_cost_medium():
    """Test formatting medium costs."""
    assert format_cost(0.5) == "$0.5000"
    assert format_cost(1.5) == "$1.5000"


def test_format_cost_large():
    """Test formatting large costs."""
    assert format_cost(10.0) == "$10.0000"
    assert format_cost(100.5) == "$100.5000"


def test_estimate_tokens_empty():
    """Test with empty string."""
    assert estimate_tokens("") == 1  # Minimum 1


def test_estimate_tokens_short():
    """Test with short text."""
    tokens = estimate_tokens("Hello")
    assert tokens > 0


def test_estimate_tokens_long():
    """Test with longer text."""
    text = "This is a longer sentence with multiple words"
    tokens = estimate_tokens(text)
    assert tokens == len(text) // 4


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
