import pytest

from cascadeflow.config import ModelConfig
from cascadeflow.providers.base import PROVIDER_CAPABILITIES


@pytest.mark.parametrize(
    "provider",
    [
        "deepseek",
        "DeepSeek",
        "openrouter",
        "OpenRouter",
    ],
)
def test_model_config_provider_allows_supported_providers(provider: str) -> None:
    config = ModelConfig(name="x", provider=provider, cost=0.0)
    assert config.provider == provider.lower()


def test_model_config_provider_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError, match="Provider must be one of"):
        ModelConfig(name="x", provider="unknown_provider", cost=0.0)


def test_model_config_provider_allows_all_provider_capability_keys() -> None:
    for provider in PROVIDER_CAPABILITIES:
        config = ModelConfig(name="x", provider=provider, cost=0.0)
        assert config.provider == provider
