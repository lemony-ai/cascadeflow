"""Tests for shared harness pricing/energy profiles."""

from __future__ import annotations

import pytest

import cascadeflow.harness.instrument as instrument_mod
import cascadeflow.integrations.crewai as crewai_mod
import cascadeflow.integrations.openai_agents as openai_agents_mod
from cascadeflow.harness.pricing import OPENAI_MODEL_POOL, estimate_cost, estimate_energy, model_total_price


def test_shared_estimate_cost_known_models() -> None:
    assert estimate_cost("gpt-4o-mini", 1_000_000, 1_000_000) == pytest.approx(0.75)
    assert estimate_cost("gpt-5", 1_000_000, 1_000_000) == pytest.approx(11.25)
    assert estimate_cost("claude-sonnet-4", 1_000_000, 1_000_000) == pytest.approx(18.0)


def test_shared_estimate_energy_defaults_for_unknown() -> None:
    # default coeff=1.0, output weight=1.5
    assert estimate_energy("unknown-model", 100, 100) == pytest.approx(250.0)


def test_openai_pool_is_openai_only() -> None:
    assert "gpt-4o" in OPENAI_MODEL_POOL
    assert "gpt-5" in OPENAI_MODEL_POOL
    assert "claude-sonnet-4" not in OPENAI_MODEL_POOL


def test_integration_estimators_use_shared_profiles() -> None:
    model = "gpt-5-mini"
    input_tokens = 12_345
    output_tokens = 6_789

    shared_cost = estimate_cost(model, input_tokens, output_tokens)
    shared_energy = estimate_energy(model, input_tokens, output_tokens)

    assert instrument_mod._estimate_cost(model, input_tokens, output_tokens) == pytest.approx(shared_cost)
    assert crewai_mod._estimate_cost(model, input_tokens, output_tokens) == pytest.approx(shared_cost)
    assert openai_agents_mod._estimate_cost(model, input_tokens, output_tokens) == pytest.approx(shared_cost)

    assert instrument_mod._estimate_energy(model, input_tokens, output_tokens) == pytest.approx(shared_energy)
    assert crewai_mod._estimate_energy(model, input_tokens, output_tokens) == pytest.approx(shared_energy)
    assert openai_agents_mod._estimate_energy(model, input_tokens, output_tokens) == pytest.approx(shared_energy)


def test_openai_agents_total_price_uses_shared_profiles() -> None:
    assert openai_agents_mod._total_model_price("gpt-5") == pytest.approx(model_total_price("gpt-5"))
    assert openai_agents_mod._total_model_price("gpt-4o-mini") == pytest.approx(model_total_price("gpt-4o-mini"))

