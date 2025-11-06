"""Tests for custom exceptions."""

import pytest

from cascadeflow import (
    BudgetExceededError,
    ModelError,
    ProviderError,
    QualityThresholdError,
    cascadeflowError,
)


def test_base_exception():
    """Test base cascadeflowError."""
    error = cascadeflowError("Test error")
    assert "Test error" in str(error)


def test_budget_exceeded_error():
    """Test BudgetExceededError creation and attributes."""
    error = BudgetExceededError("Budget exceeded", remaining=0.5)

    assert "Budget exceeded" in str(error)
    assert error.remaining == 0.5
    assert isinstance(error, cascadeflowError)


def test_quality_threshold_error():
    """Test QualityThresholdError."""
    error = QualityThresholdError("Quality too low")

    assert "Quality too low" in str(error)
    assert isinstance(error, cascadeflowError)


def test_provider_error():
    """Test ProviderError with provider attribute."""
    error = ProviderError("API failed", provider="openai")

    assert "API failed" in str(error)
    assert error.provider == "openai"
    assert isinstance(error, cascadeflowError)


def test_model_error():
    """Test ModelError with model and provider attributes."""
    error = ModelError("Model failed", model="gpt-4", provider="openai")

    assert "Model failed" in str(error)
    assert error.model == "gpt-4"
    assert error.provider == "openai"
    assert isinstance(error, cascadeflowError)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
