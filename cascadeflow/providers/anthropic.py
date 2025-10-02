"""Anthropic Claude provider implementation."""

import os
import time
from typing import Optional, Dict, Any

import httpx

from .base import BaseProvider, ModelResponse
from ..exceptions import ProviderError, ModelError


class AnthropicProvider(BaseProvider):
    """
    Anthropic provider for Claude models.

    Supports: Claude 3 (Opus, Sonnet, Haiku), Claude 3.5, etc.

    Example:
        >>> provider = AnthropicProvider(api_key="sk-ant-...")
        >>> response = await provider.complete(
        ...     prompt="What is AI?",
        ...     model="claude-3-sonnet-20240229"
        ... )
        >>> print(response.content)
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Anthropic provider.

        Args:
            api_key: Anthropic API key. If None, reads from ANTHROPIC_API_KEY env var.
        """
        # Call parent init to load API key
        super().__init__(api_key)

        # Verify API key is set
        if not self.api_key:
            raise ValueError(
                "Anthropic API key not found. Please set ANTHROPIC_API_KEY environment "
                "variable or pass api_key parameter."
            )

        # Now initialize HTTP client with the loaded API key
        self.base_url = "https://api.anthropic.com/v1"
        self.api_version = "2023-06-01"
        self.client = httpx.AsyncClient(
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": self.api_version,
                "Content-Type": "application/json"
            },
            timeout=60.0
        )

    def _load_api_key(self) -> Optional[str]:
        """Load API key from environment."""
        return os.getenv("ANTHROPIC_API_KEY")

    async def complete(
            self,
            prompt: str,
            model: str,
            max_tokens: int = 4096,
            temperature: float = 0.7,
            system_prompt: Optional[str] = None,
            **kwargs
    ) -> ModelResponse:
        """
        Complete a prompt using Anthropic API.

        Args:
            prompt: User prompt
            model: Model name (e.g., 'claude-3-sonnet-20240229', 'claude-3-opus-20240229')
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-1)
            system_prompt: Optional system prompt
            **kwargs: Additional Anthropic parameters

        Returns:
            ModelResponse with standardized format

        Raises:
            ProviderError: If API call fails
            ModelError: If model execution fails
        """
        start_time = time.time()

        # Build request payload (Anthropic format is different from OpenAI)
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            **kwargs
        }

        # Add system prompt if provided
        if system_prompt:
            payload["system"] = system_prompt

        try:
            # Make API request
            response = await self.client.post(
                f"{self.base_url}/messages",
                json=payload
            )
            response.raise_for_status()

            data = response.json()

            # Extract response (Anthropic format)
            content = data["content"][0]["text"]

            # Anthropic doesn't return token counts in response
            # Estimate tokens
            prompt_tokens = len(prompt) // 4
            completion_tokens = len(content) // 4
            tokens_used = prompt_tokens + completion_tokens

            # Calculate latency
            latency_ms = (time.time() - start_time) * 1000

            # Calculate cost
            cost = self.estimate_cost(tokens_used, model)

            # Calculate confidence
            confidence = self.calculate_confidence(
                content,
                {"stop_reason": data.get("stop_reason")}
            )

            return ModelResponse(
                content=content,
                model=model,
                provider="anthropic",
                cost=cost,
                tokens_used=tokens_used,
                confidence=confidence,
                latency_ms=latency_ms,
                metadata={
                    "stop_reason": data.get("stop_reason"),
                    "id": data.get("id"),
                }
            )

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise ProviderError(
                    "Invalid Anthropic API key",
                    provider="anthropic",
                    original_error=e
                )
            elif e.response.status_code == 429:
                raise ProviderError(
                    "Anthropic rate limit exceeded",
                    provider="anthropic",
                    original_error=e
                )
            else:
                raise ProviderError(
                    f"Anthropic API error: {e.response.status_code}",
                    provider="anthropic",
                    original_error=e
                )
        except httpx.RequestError as e:
            raise ProviderError(
                "Failed to connect to Anthropic API",
                provider="anthropic",
                original_error=e
            )
        except (KeyError, IndexError) as e:
            raise ModelError(
                f"Failed to parse Anthropic response: {e}",
                model=model,
                provider="anthropic"
            )

    def estimate_cost(self, tokens: int, model: str) -> float:
        """
        Estimate cost for Anthropic model.

        Args:
            tokens: Total tokens (prompt + completion)
            model: Model name

        Returns:
            Estimated cost in USD
        """
        # Anthropic pricing (as of 2024)
        rates = {
            "claude-3-opus": 0.015,       # $0.015 per 1K tokens
            "claude-3-sonnet": 0.003,     # $0.003 per 1K tokens
            "claude-3-haiku": 0.00025,    # $0.00025 per 1K tokens
            "claude-3-5-sonnet": 0.003,   # $0.003 per 1K tokens
        }

        # Find matching rate
        for model_prefix, rate in rates.items():
            if model.startswith(model_prefix):
                return (tokens / 1000) * rate

        # Default to Sonnet pricing if unknown
        return (tokens / 1000) * 0.003

    def calculate_confidence(
            self,
            response: str,
            metadata: Optional[Dict[str, Any]] = None
    ) -> float:
        """
        Calculate confidence score for Anthropic response.

        Args:
            response: Model response text
            metadata: Response metadata from API

        Returns:
            Confidence score (0-1)
        """
        # Start with base confidence
        confidence = super().calculate_confidence(response)

        if metadata:
            # Adjust based on stop_reason
            stop_reason = metadata.get("stop_reason")

            if stop_reason == "end_turn":
                # Natural completion - strong signal of quality
                # Boost confidence significantly since model chose to stop
                confidence = min(1.0, confidence + 0.4)
            elif stop_reason == "max_tokens":
                # Hit max tokens - might be incomplete
                confidence = max(0.5, confidence - 0.1)

        return confidence

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.client.aclose()