"""Tests for cost calculator token usage paths."""

from types import SimpleNamespace

import pytest

from cascadeflow.schema.config import ModelConfig
from cascadeflow.telemetry.cost_calculator import CostCalculator


@pytest.fixture
def calculator(monkeypatch):
    """Create cost calculator with deterministic fallback pricing."""
    from cascadeflow.integrations import litellm as litellm_integration

    monkeypatch.setattr(litellm_integration, "LITELLM_AVAILABLE", False)

    drafter = ModelConfig(name="drafter-test", provider="custom", cost=1.0)
    verifier = ModelConfig(name="verifier-test", provider="custom", cost=2.0)
    return CostCalculator(drafter=drafter, verifier=verifier, verbose=False)


def test_calculate_accepted_uses_prompt_completion_tokens(calculator):
    """Accepted drafts should use explicit prompt/completion tokens."""
    result = SimpleNamespace(
        draft_accepted=True,
        metadata={
            "draft_prompt_tokens": 100,
            "draft_completion_tokens": 50,
        },
    )

    breakdown = calculator.calculate(result)

    assert breakdown.draft_cost == pytest.approx(0.15)
    assert breakdown.verifier_cost == pytest.approx(0.0)
    assert breakdown.total_cost == pytest.approx(0.15)
    assert breakdown.cost_saved == pytest.approx(0.15)


def test_calculate_rejected_uses_draft_and_verifier_tokens(calculator):
    """Rejected drafts should aggregate draft + verifier costs."""
    result = SimpleNamespace(
        draft_accepted=False,
        metadata={
            "draft_prompt_tokens": 100,
            "draft_completion_tokens": 20,
            "verifier_prompt_tokens": 100,
            "verifier_completion_tokens": 40,
        },
    )

    breakdown = calculator.calculate(result)

    assert breakdown.draft_cost == pytest.approx(0.12)
    assert breakdown.verifier_cost == pytest.approx(0.28)
    assert breakdown.total_cost == pytest.approx(0.40)
    assert breakdown.cost_saved == pytest.approx(-0.12)


def test_fallback_cost_estimates_openai(monkeypatch):
    """Fallback pricing should estimate non-zero cost when model.cost is zero."""
    from cascadeflow.integrations import litellm as litellm_integration

    monkeypatch.setattr(litellm_integration, "LITELLM_AVAILABLE", False)

    model = ModelConfig(name="gpt-5-mini", provider="openai", cost=0.0)
    calculator = CostCalculator(drafter=model, verifier=model, verbose=False)

    cost = calculator._calculate_model_cost(model, tokens=1000, input_tokens=700, output_tokens=300)

    assert cost > 0


def test_fallback_cost_estimates_anthropic(monkeypatch):
    """Fallback pricing should estimate non-zero cost for Anthropic models with zero cost."""
    from cascadeflow.integrations import litellm as litellm_integration

    monkeypatch.setattr(litellm_integration, "LITELLM_AVAILABLE", False)

    model = ModelConfig(name="claude-sonnet-4", provider="anthropic", cost=0.0)
    calculator = CostCalculator(drafter=model, verifier=model, verbose=False)

    cost = calculator._calculate_model_cost(
        model, tokens=2000, input_tokens=1200, output_tokens=800
    )

    assert cost > 0
