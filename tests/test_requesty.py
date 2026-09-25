"""Tests for Requesty provider."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cascadeflow.providers.base import ModelResponse
from cascadeflow.providers.requesty import RequestyProvider


@pytest.fixture
def mock_env():
    """Mock environment variables."""
    with patch.dict(os.environ, {"REQUESTY_API_KEY": "test_key"}):
        yield


@pytest.fixture
def requesty_provider(mock_env):
    """Create Requesty provider for testing."""
    return RequestyProvider()


def _json_response(payload):
    response = MagicMock()
    response.json.return_value = payload
    response.raise_for_status = MagicMock()
    return response


class TestRequestyProvider:
    """Tests for Requesty provider."""

    def test_init_with_api_key(self):
        provider = RequestyProvider(api_key="explicit_key")
        assert provider.api_key == "explicit_key"
        assert provider.base_url == "https://router.requesty.ai/v1"

    def test_init_from_env(self, mock_env):
        provider = RequestyProvider()
        assert provider.api_key == "test_key"

    def test_init_custom_base_url(self, mock_env):
        provider = RequestyProvider(base_url="https://router.eu.requesty.ai/v1")
        assert provider.base_url == "https://router.eu.requesty.ai/v1"

    def test_init_no_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="Requesty API key not found"):
                RequestyProvider()

    def test_registered_in_provider_registry(self):
        from cascadeflow.providers import PROVIDER_REGISTRY

        assert PROVIDER_REGISTRY["requesty"] is RequestyProvider

    @pytest.mark.asyncio
    async def test_complete_uses_reported_cost(self, requesty_provider):
        payload = {
            "model": "gpt-4o-mini-2024-07-18",
            "choices": [{"message": {"content": "Hello there."}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "cost": 0.0000135},
        }
        with patch.object(requesty_provider.client, "post", new=AsyncMock()) as mock_post:
            mock_post.return_value = _json_response(payload)

            result = await requesty_provider.complete(prompt="Hi", model="openai/gpt-4o-mini")

            assert isinstance(result, ModelResponse)
            assert result.content == "Hello there."
            assert result.provider == "requesty"
            assert result.tokens_used == 30
            assert result.cost == pytest.approx(0.0000135)
            assert mock_post.call_args.args[0] == "https://router.requesty.ai/v1/chat/completions"

    @pytest.mark.asyncio
    async def test_complete_estimates_cost_without_usage_cost(self, requesty_provider):
        payload = {
            "choices": [{"message": {"content": "Hello there."}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000},
        }
        with patch.object(requesty_provider.client, "post", new=AsyncMock()) as mock_post:
            mock_post.return_value = _json_response(payload)

            result = await requesty_provider.complete(prompt="Hi", model="openai/gpt-4o-mini")

            # $0.15 input + $0.60 output per 1M tokens
            assert result.cost == pytest.approx(0.75)

    @pytest.mark.asyncio
    async def test_fetch_available_models_merges_managed_first(self, requesty_provider):
        managed = {"data": [{"id": "claude-sonnet-4-5", "api": "chat"}]}
        catalog = {
            "data": [
                {"id": "openai/gpt-4o-mini", "api": "chat"},
                {"id": "claude-sonnet-4-5", "api": "chat"},
            ]
        }
        with patch.object(requesty_provider.client, "get", new=AsyncMock()) as mock_get:
            mock_get.side_effect = [_json_response(managed), _json_response(catalog)]

            models = await requesty_provider.fetch_available_models()

            assert [m["id"] for m in models] == ["claude-sonnet-4-5", "openai/gpt-4o-mini"]
            assert mock_get.call_args_list[0].args[0].endswith("/models/managed")

            # Second call is served from cache
            await requesty_provider.fetch_available_models()
            assert mock_get.call_count == 2

    @pytest.mark.asyncio
    async def test_fetch_available_models_handles_errors(self, requesty_provider):
        with patch.object(requesty_provider.client, "get", new=AsyncMock()) as mock_get:
            mock_get.side_effect = Exception("network error")

            models = await requesty_provider.fetch_available_models()

            assert models == []
