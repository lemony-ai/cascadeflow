"""Integration-level tests for the Eden AI provider.

These cover the *configuration path* rather than the provider in isolation:
``ModelConfig`` validation, ``PROVIDER_REGISTRY`` resolution and ``CascadeAgent``
wiring. The direct-provider unit tests in ``test_edenai.py`` instantiate
``EdenAIProvider`` themselves, so they cannot catch a provider that is
implemented but not registered in the configuration layer.
"""

import os
from unittest.mock import patch

import pytest

from cascadeflow.config import ModelConfig
from cascadeflow.providers import PROVIDER_REGISTRY
from cascadeflow.providers.base import PROVIDER_CAPABILITIES
from cascadeflow.providers.edenai import EdenAIProvider


@pytest.fixture
def mock_env():
    """Mock environment variables."""
    with patch.dict(os.environ, {"EDENAI_API_KEY": "eden_test_key_12345"}):
        yield


# ---------------------------------------------------------------------------
# ModelConfig validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("provider", ["edenai", "EdenAI", "EDENAI"])
def test_model_config_accepts_edenai(provider: str) -> None:
    """``ModelConfig`` must accept 'edenai', case-insensitively."""
    config = ModelConfig(name="anthropic/claude-haiku-4-5", provider=provider, cost=0.0)
    assert config.provider == "edenai"


# ---------------------------------------------------------------------------
# Registry resolution
# ---------------------------------------------------------------------------


def test_provider_registry_resolves_edenai() -> None:
    """The registry must map the validated provider key to EdenAIProvider."""
    config = ModelConfig(name="openai/gpt-4o-mini", provider="edenai", cost=0.0)
    assert config.provider in PROVIDER_REGISTRY
    assert PROVIDER_REGISTRY[config.provider] is EdenAIProvider


# ---------------------------------------------------------------------------
# Capability matrix
# ---------------------------------------------------------------------------


def test_edenai_declared_in_capability_matrix() -> None:
    """Eden AI must declare the capabilities it actually implements."""
    capabilities = PROVIDER_CAPABILITIES["edenai"]
    assert capabilities["supports_streaming"] is True
    assert capabilities["supports_tools"] is True
    # Eden AI returns the real per-request cost in the response body.
    assert capabilities["has_cost_tracking"] is True
    # Logprobs support varies per underlying model, so it is reported False.
    assert capabilities["supports_logprobs"] is False
    assert capabilities["max_top_logprobs"] == 0


def test_capability_matrix_matches_provider_implementation(mock_env) -> None:
    """Guard against the matrix drifting from the provider implementation."""
    provider = EdenAIProvider()
    capabilities = PROVIDER_CAPABILITIES["edenai"]
    assert provider._check_logprobs_support() == capabilities["supports_logprobs"]


# ---------------------------------------------------------------------------
# CascadeAgent wiring
# ---------------------------------------------------------------------------


def test_cascade_agent_initializes_edenai_provider(mock_env) -> None:
    """A CascadeAgent configured with provider='edenai' must wire up the provider."""
    from cascadeflow import CascadeAgent

    models = [
        ModelConfig(name="openai/gpt-4o-mini", provider="edenai", cost=0.00015),
        ModelConfig(name="anthropic/claude-sonnet-4-5", provider="edenai", cost=0.003),
    ]
    agent = CascadeAgent(models=models)

    assert "edenai" in agent.providers
    assert isinstance(agent.providers["edenai"], EdenAIProvider)
    # Multi-instance lookup: one provider instance per configured model.
    for model in models:
        assert isinstance(agent._get_provider(model), EdenAIProvider)


def test_cascade_agent_honours_custom_base_url(mock_env) -> None:
    """The EU gateway (or any custom base_url) must reach the provider instance."""
    from cascadeflow import CascadeAgent

    model = ModelConfig(
        name="openai/gpt-4o-mini",
        provider="edenai",
        cost=0.00015,
        base_url="https://api.eu.edenai.run/v3",
    )
    agent = CascadeAgent(models=[model])

    assert agent._get_provider(model).base_url == "https://api.eu.edenai.run/v3"
