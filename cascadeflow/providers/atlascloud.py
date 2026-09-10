"""Atlas Cloud provider implementation.

Atlas Cloud exposes an OpenAI-compatible chat completions API, so the provider
reuses the OpenAI provider implementation with Atlas-specific defaults.

Environment Variables:
    ATLASCLOUD_API_KEY: Your Atlas Cloud API key

Models:
    - qwen/qwen3.5-flash: Fast default chat model
    - deepseek-ai/deepseek-v4-pro: Reasoning-capable chat model
"""

import os
from typing import Any, Optional

from ..exceptions import ModelError, ProviderError
from .base import ModelResponse
from .openai import OpenAIProvider


class AtlasCloudProvider(OpenAIProvider):
    """Atlas Cloud provider using the OpenAI-compatible API."""

    BASE_URL = "https://api.atlascloud.ai/v1"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        **kwargs,
    ):
        """
        Initialize Atlas Cloud provider.

        Args:
            api_key: Atlas Cloud API key (defaults to ATLASCLOUD_API_KEY env var)
            base_url: Custom base URL (defaults to Atlas Cloud API)
            **kwargs: Additional OpenAI provider options
        """
        atlascloud_api_key = api_key or os.getenv("ATLASCLOUD_API_KEY")

        if not atlascloud_api_key:
            raise ValueError(
                "Atlas Cloud API key not found. "
                "Set ATLASCLOUD_API_KEY environment variable or pass api_key parameter."
            )

        super().__init__(api_key=atlascloud_api_key, **kwargs)
        self.base_url = base_url or self.BASE_URL
        # Atlas pricing is not represented by LiteLLM's OpenAI model catalog.
        # Report untracked cost instead of attributing OpenAI estimates.
        self._litellm_cost_provider = None
        self._use_litellm_pricing = False
        self._litellm_provider_prefix = None

    @property
    def name(self) -> str:
        """Provider name."""
        return "atlascloud"

    def _check_logprobs_support(self) -> bool:
        """Atlas Cloud does not currently guarantee OpenAI logprobs semantics."""
        return False

    def _get_litellm_prefix(self) -> Optional[str]:
        """Atlas model IDs must not be rewritten as OpenAI model IDs."""
        return None

    def estimate_cost(
        self,
        tokens: int,
        model: str,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
    ) -> float:
        """Return an explicit untracked cost until Atlas pricing is available locally."""
        return 0.0

    def _attribute_error(self, error: Exception) -> None:
        if isinstance(error, (ProviderError, ModelError)):
            error.provider = self.name
            error.args = (str(error).replace("OpenAI", "Atlas Cloud"),)

    async def _complete_impl(
        self,
        prompt: str,
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> ModelResponse:
        try:
            response = await super()._complete_impl(
                prompt=prompt,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system_prompt=system_prompt,
                **kwargs,
            )
        except (ProviderError, ModelError) as error:
            self._attribute_error(error)
            raise
        response.provider = self.name
        return response

    async def complete_with_tools(self, *args: Any, **kwargs: Any) -> ModelResponse:
        try:
            response = await super().complete_with_tools(*args, **kwargs)
        except (ProviderError, ModelError) as error:
            self._attribute_error(error)
            raise
        response.provider = self.name
        return response
