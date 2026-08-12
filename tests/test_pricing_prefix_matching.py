"""Tests for longest-prefix resolution of model pricing.

Pricing tables are keyed by model family but callers pass date-pinned model ids.
Resolving those by first prefix hit made the result depend on dict insertion
order, pricing ``gpt-4o-mini-2024-07-18`` as ``gpt-4o`` (and, in the LiteLLM
fallback table, as ``gpt-4``). Each table below is checked against the family it
should actually resolve to.
"""

import pytest

from cascadeflow.integrations.litellm import LiteLLMCostProvider
from cascadeflow.pricing import PriceBook, PricingResolver, longest_prefix_match
from cascadeflow.providers.openrouter import OpenRouterProvider
from cascadeflow.schema.config import ModelConfig
from cascadeflow.schema.usage import Usage
from cascadeflow.telemetry.cost_calculator import CostCalculator

ONE_MILLION = 1_000_000


# ---------------------------------------------------------------------------
# helper
# ---------------------------------------------------------------------------


def test_longest_prefix_match_prefers_the_more_specific_family():
    candidates = ["gpt-4", "gpt-4o", "gpt-4o-mini"]

    assert longest_prefix_match("gpt-4o-mini-2024-07-18", candidates) == "gpt-4o-mini"
    assert longest_prefix_match("gpt-4o-2024-08-06", candidates) == "gpt-4o"
    assert longest_prefix_match("gpt-4-0613", candidates) == "gpt-4"


def test_longest_prefix_match_is_insertion_order_independent():
    """Reversing the table must not change which family wins."""
    forward = ["gpt-4o", "gpt-4o-mini"]

    assert longest_prefix_match("gpt-4o-mini-2024-07-18", forward) == "gpt-4o-mini"
    assert longest_prefix_match("gpt-4o-mini-2024-07-18", list(reversed(forward))) == "gpt-4o-mini"


def test_longest_prefix_match_returns_none_without_a_match():
    assert longest_prefix_match("claude-3-opus", ["gpt-4o", "gpt-5"]) is None


# ---------------------------------------------------------------------------
# PriceBook (used by CascadeAgent via PricingResolver)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("pinned", "family"),
    [
        ("gpt-4o-mini-2024-07-18", "gpt-4o-mini"),
        ("gpt-4o-2024-08-06", "gpt-4o"),
        ("o1-mini-2024-09-12", "o1-mini"),
        ("gpt-5-mini-2025-08-07", "gpt-5-mini"),
        ("gpt-5-nano-2025-08-07", "gpt-5-nano"),
    ],
)
def test_pricebook_resolves_pinned_ids_to_their_own_family(pinned, family):
    pricebook = PriceBook()

    assert pricebook.get(pinned) == pricebook.get(family)


def test_pricebook_runtime_entry_is_not_shadowed_by_a_shorter_family():
    """update() must win for its own ids even when a shorter key exists."""
    pricebook = PriceBook()
    pricebook.update("gpt-4o-mini-high", input_per_1k=0.002, output_per_1k=0.008)

    price = pricebook.get("gpt-4o-mini-high-2025-01-01")

    assert price.input_per_1k == pytest.approx(0.002)
    assert price.output_per_1k == pytest.approx(0.008)


def test_cascade_savings_are_not_erased_by_drafter_mispricing():
    """A cheap pinned drafter must stay cheap against a pinned verifier.

    Both ids previously collapsed onto gpt-4o, reporting 0% savings for a
    cascade that actually saves ~94%.
    """
    resolver = PricingResolver()
    usage = Usage(input_tokens=500, output_tokens=300)

    drafter_cost = resolver.resolve_cost(model="gpt-4o-mini-2024-07-18", usage=usage)
    verifier_cost = resolver.resolve_cost(model="gpt-4o-2024-08-06", usage=usage)

    assert drafter_cost == pytest.approx(500 / 1000 * 0.00015 + 300 / 1000 * 0.0006)
    assert drafter_cost < verifier_cost
    assert (verifier_cost - drafter_cost) / verifier_cost > 0.9


# ---------------------------------------------------------------------------
# LiteLLM fallback table (active whenever litellm is not installed)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("pinned", "family"),
    [
        ("gpt-4o-mini-2024-07-18", "gpt-4o-mini"),
        ("gpt-4o-2024-08-06", "gpt-4o"),
        ("gpt-4-turbo-2024-04-09", "gpt-4-turbo"),
    ],
)
def test_litellm_fallback_prices_pinned_ids_as_their_own_family(monkeypatch, pinned, family):
    from cascadeflow.integrations import litellm as litellm_integration

    monkeypatch.setattr(litellm_integration, "LITELLM_AVAILABLE", False)
    provider = LiteLLMCostProvider()

    pinned_cost = provider.calculate_cost(pinned, ONE_MILLION, ONE_MILLION)
    family_cost = provider.calculate_cost(family, ONE_MILLION, ONE_MILLION)

    assert pinned_cost == pytest.approx(family_cost)


def test_litellm_fallback_keeps_default_for_unknown_models(monkeypatch):
    from cascadeflow.integrations import litellm as litellm_integration

    monkeypatch.setattr(litellm_integration, "LITELLM_AVAILABLE", False)
    provider = LiteLLMCostProvider()

    cost = provider.calculate_cost("some-unlisted-model", ONE_MILLION, ONE_MILLION)

    assert cost == pytest.approx(1.0 + 2.0)


# ---------------------------------------------------------------------------
# CostCalculator provider-aware fallback
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("model", "expected_input", "expected_output"),
    [
        ("gpt-4o-mini", 0.00015, 0.0006),
        ("gpt-4o-mini-2024-07-18", 0.00015, 0.0006),
        ("gpt-5-mini", 0.00025, 0.002),
        ("gpt-5-nano", 0.00005, 0.0004),
        ("gpt-4o", 0.0025, 0.010),
    ],
)
def test_cost_calculator_fallback_matches_published_openai_rates(
    model, expected_input, expected_output
):
    config = ModelConfig(name=model, provider="openai", cost=0.0)

    cost = CostCalculator._estimate_fallback_cost(
        config, tokens=0, input_tokens=ONE_MILLION, output_tokens=ONE_MILLION
    )

    expected = ONE_MILLION / 1000 * (expected_input + expected_output)
    assert cost == pytest.approx(expected)


def test_cost_calculator_fallback_agrees_with_openai_provider_table():
    """The telemetry fallback must not disagree with the provider pricebook."""
    from cascadeflow.providers.openai import _openai_model_pricing

    for model in ("gpt-4o-mini", "gpt-5-mini", "gpt-5-nano", "gpt-4o", "gpt-4-turbo"):
        config = ModelConfig(name=model, provider="openai", cost=0.0)
        rates = _openai_model_pricing(model)

        cost = CostCalculator._estimate_fallback_cost(
            config, tokens=0, input_tokens=ONE_MILLION, output_tokens=ONE_MILLION
        )

        expected = ONE_MILLION / 1000 * (rates["input"] + rates["output"])
        assert cost == pytest.approx(expected), model


# ---------------------------------------------------------------------------
# OpenRouter
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("pinned", "family"),
    [
        ("openai/gpt-4o-mini-2024-07-18", "openai/gpt-4o-mini"),
        ("openai/o1-mini-2024-09-12", "openai/o1-mini"),
    ],
)
def test_openrouter_prices_pinned_ids_as_their_own_family(pinned, family):
    provider = OpenRouterProvider.__new__(OpenRouterProvider)

    pinned_cost = provider._calculate_cost(pinned, ONE_MILLION, ONE_MILLION)
    family_cost = provider._calculate_cost(family, ONE_MILLION, ONE_MILLION)

    assert pinned_cost == pytest.approx(family_cost)


def test_openrouter_keeps_default_for_unknown_models():
    provider = OpenRouterProvider.__new__(OpenRouterProvider)

    cost = provider._calculate_cost("some/unlisted-model", ONE_MILLION, ONE_MILLION)

    assert cost == pytest.approx(0.15 + 0.6)
