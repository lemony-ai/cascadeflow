"""Tests for Atlas Cloud provider."""

import os
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from cascadeflow.exceptions import ProviderError
from cascadeflow.providers import PROVIDER_CAPABILITIES, PROVIDER_REGISTRY
from cascadeflow.providers.atlascloud import AtlasCloudProvider
from cascadeflow.schema.config import ModelConfig


def test_init_with_api_key():
    """Test initialization with explicit API key."""
    provider = AtlasCloudProvider(api_key="atlas-test-key")

    assert provider.api_key == "atlas-test-key"
    assert provider.base_url == "https://api.atlascloud.ai/v1"
    assert provider.name == "atlascloud"


def test_init_from_env():
    """Test initialization from ATLASCLOUD_API_KEY."""
    with patch.dict(os.environ, {"ATLASCLOUD_API_KEY": "atlas-env-key"}, clear=True):
        provider = AtlasCloudProvider()

    assert provider.api_key == "atlas-env-key"
    assert provider.base_url == "https://api.atlascloud.ai/v1"


def test_init_no_api_key():
    """Test initialization fails without Atlas Cloud API key."""
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="Atlas Cloud API key not found"):
            AtlasCloudProvider()


def test_custom_base_url():
    """Test custom Atlas Cloud-compatible base URL."""
    provider = AtlasCloudProvider(api_key="atlas-test-key", base_url="https://proxy.test/v1")

    assert provider.base_url == "https://proxy.test/v1"


def test_registered_provider():
    """Test Atlas Cloud is registered for cascade agents."""
    assert PROVIDER_REGISTRY["atlascloud"] is AtlasCloudProvider


def test_model_config_and_capabilities():
    config = ModelConfig(name="qwen/qwen3.5-flash", provider="atlascloud", cost=0)

    assert config.provider == "atlascloud"
    assert PROVIDER_CAPABILITIES["atlascloud"] == {
        "supports_logprobs": False,
        "supports_streaming": True,
        "supports_tools": True,
        "max_top_logprobs": 0,
        "has_cost_tracking": False,
    }


@pytest.mark.asyncio
async def test_registry_provider_response_attribution():
    config = ModelConfig(name="qwen/qwen3.5-flash", provider="atlascloud", cost=0)
    provider = PROVIDER_REGISTRY[config.provider](api_key="atlas-test-key")
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3},
    }
    provider.client.post = AsyncMock(return_value=response)

    result = await provider.complete(prompt="hello", model=config.name, logprobs=False)

    assert provider.client.post.await_args.args[0] == (
        "https://api.atlascloud.ai/v1/chat/completions"
    )
    assert result.provider == "atlascloud"
    assert result.cost == 0.0


@pytest.mark.asyncio
async def test_error_attribution_uses_atlascloud():
    provider = AtlasCloudProvider(api_key="atlas-test-key")
    request = httpx.Request("POST", "https://api.atlascloud.ai/v1/chat/completions")
    response = httpx.Response(401, request=request)
    provider.client.post = AsyncMock(return_value=response)

    with pytest.raises(ProviderError) as exc_info:
        await provider.complete(prompt="hello", model="qwen/qwen3.5-flash", logprobs=False)

    assert exc_info.value.provider == "atlascloud"
    assert "Atlas Cloud" in str(exc_info.value)


def test_cost_is_explicitly_untracked():
    provider = AtlasCloudProvider(api_key="atlas-test-key")

    assert provider._use_litellm_pricing is False
    assert provider.calculate_accurate_cost(
        model="qwen/qwen3.5-flash", prompt_tokens=100, completion_tokens=50
    ) == 0.0
