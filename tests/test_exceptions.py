"""Tests for custom exceptions."""

import pytest
from cascadeflow.exceptions import (
    CascadeFlowError,
    BudgetExceededError,
    RateLimitError,
    ProviderError,
    ModelError,
)


def test_cascade_flow_error():
    """Test base CascadeFlowError."""
    error = CascadeFlowError("Test error")
    assert str(error) == "Test error"
    assert isinstance(error, Exception)


def test_budget_exceeded_error():
    """Test BudgetExceededError with attributes."""
    error = BudgetExceededError(
        "Budget exceeded",
        current=0.15,
        limit=0.10,
        remaining=0.0
    )

    assert str(error) == "Budget exceeded"
    assert error.current == 0.15
    assert error.limit == 0.10
    assert error.remaining == 0.0


def test_rate_limit_error():
    """Test RateLimitError with retry_after."""
    error = RateLimitError("Rate limit hit", retry_after=3600)

    assert str(error) == "Rate limit hit"
    assert error.retry_after == 3600


def test_provider_error():
    """Test ProviderError with provider info."""
    original = ValueError("Connection failed")
    error = ProviderError(
        "Provider unavailable",
        provider="openai",
        original_error=original
    )

    assert str(error) == "Provider unavailable"
    assert error.provider == "openai"
    assert error.original_error == original


def test_model_error():
    """Test ModelError with model info."""
    error = ModelError(
        "Model failed",
        model="gpt-4",
        provider="openai"
    )

    assert str(error) == "Model failed"
    assert error.model == "gpt-4"
    assert error.provider == "openai"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])