"""DeepSeek provider implementation.

DeepSeek uses an OpenAI-compatible API, making it easy to integrate.
The provider extends the OpenAI provider with DeepSeek-specific configuration.

Environment Variables:
    DEEPSEEK_API_KEY: Your DeepSeek API key

Models:
    - deepseek-coder: Specialized for code generation and understanding
    - deepseek-chat: General-purpose chat model

Example:
    >>> from cascadeflow import CascadeAgent, ModelConfig
    >>> agent = CascadeAgent(
    ...     models=[
    ...         ModelConfig(name="deepseek-coder", provider="deepseek", cost=0.00014),
    ...     ]
    ... )
"""

import os
from typing import Optional

from .openai import OpenAIProvider


class DeepSeekProvider(OpenAIProvider):
    """
    DeepSeek provider using OpenAI-compatible API.

    DeepSeek models are particularly strong at:
    - Code generation and understanding
    - Mathematical reasoning
    - General chat

    The API is fully compatible with OpenAI's API format.
    All methods are inherited from OpenAIProvider - only the
    base URL and API key source are different.
    """

    # DeepSeek API base URL
    BASE_URL = "https://api.deepseek.com"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        **kwargs,
    ):
        """
        Initialize DeepSeek provider.

        Args:
            api_key: DeepSeek API key (defaults to DEEPSEEK_API_KEY env var)
            base_url: Custom base URL (defaults to DeepSeek API)
            **kwargs: Additional OpenAI provider options
        """
        # Get API key from environment if not provided
        deepseek_api_key = api_key or os.getenv("DEEPSEEK_API_KEY")

        if not deepseek_api_key:
            raise ValueError(
                "DeepSeek API key not found. "
                "Set DEEPSEEK_API_KEY environment variable or pass api_key parameter."
            )

        # Initialize parent OpenAI provider with DeepSeek API key
        super().__init__(api_key=deepseek_api_key, **kwargs)

        # Override base URL to use DeepSeek API
        self.base_url = base_url or self.BASE_URL

    @property
    def name(self) -> str:
        """Provider name."""
        return "deepseek"
