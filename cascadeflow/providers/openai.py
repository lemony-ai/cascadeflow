"""OpenAI provider implementation."""

import os
import time
from typing import Optional, Dict, Any

import httpx

from .base import BaseProvider, ModelResponse
from ..exceptions import ProviderError, ModelError


class OpenAIProvider(BaseProvider):
    """
    OpenAI provider for GPT models.

    Supports: GPT-3.5, GPT-4, GPT-4 Turbo, GPT-4o, etc.

    Example:
        >>> provider = OpenAIProvider(api_key="sk-...")
        >>> response = await provider.complete(
        ...     prompt="What is AI?",
        ...     model="gpt-3.5-turbo"
        ... )
        >>> print(response.content)
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize OpenAI provider.

        Args:
            api_key: OpenAI API key. If None, reads from OPENAI_API_KEY env var.
        """
        # Call parent init to load API key
        super().__init__(api_key)

        # Verify API key is set
        if not self.api_key:
            raise ValueError(
                "OpenAI API key not found. Please set OPENAI_API_KEY environment "
                "variable or pass api_key parameter."
            )

        # Now initialize HTTP client with the loaded API key
        self.base_url = "https://api.openai.com/v1"
        self.client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            timeout=60.0
        )

    def _load_api_key(self) -> Optional[str]:
        """Load API key from environment."""
        return os.getenv("OPENAI_API_KEY")

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
        Complete a prompt using OpenAI API.

        Args:
            prompt: User prompt
            model: Model name (e.g., 'gpt-3.5-turbo', 'gpt-4')
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-2)
            system_prompt: Optional system prompt
            **kwargs: Additional OpenAI parameters

        Returns:
            ModelResponse with standardized format

        Raises:
            ProviderError: If API call fails
            ModelError: If model execution fails
        """
        start_time = time.time()

        # Build messages
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Build request payload
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            **kwargs
        }

        try:
            # Make API request
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                json=payload
            )
            response.raise_for_status()

            data = response.json()

            # Extract response
            content = data["choices"][0]["message"]["content"]
            prompt_tokens = data["usage"]["prompt_tokens"]
            completion_tokens = data["usage"]["completion_tokens"]
            tokens_used = data["usage"]["total_tokens"]

            # Calculate latency
            latency_ms = (time.time() - start_time) * 1000

            # Calculate accurate cost using input/output split
            cost = self.estimate_cost(
                tokens_used,
                model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens
            )

            # Calculate confidence
            confidence = self.calculate_confidence(
                content,
                {"finish_reason": data["choices"][0]["finish_reason"]}
            )

            return ModelResponse(
                content=content,
                model=model,
                provider="openai",
                cost=cost,
                tokens_used=tokens_used,
                confidence=confidence,
                latency_ms=latency_ms,
                metadata={
                    "finish_reason": data["choices"][0]["finish_reason"],
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                }
            )

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise ProviderError(
                    "Invalid OpenAI API key",
                    provider="openai",
                    original_error=e
                )
            elif e.response.status_code == 429:
                raise ProviderError(
                    "OpenAI rate limit exceeded",
                    provider="openai",
                    original_error=e
                )
            else:
                raise ProviderError(
                    f"OpenAI API error: {e.response.status_code}",
                    provider="openai",
                    original_error=e
                )
        except httpx.RequestError as e:
            raise ProviderError(
                "Failed to connect to OpenAI API",
                provider="openai",
                original_error=e
            )
        except (KeyError, IndexError) as e:
            raise ModelError(
                f"Failed to parse OpenAI response: {e}",
                model=model,
                provider="openai"
            )

    def estimate_cost(
            self,
            tokens: int,
            model: str,
            prompt_tokens: Optional[int] = None,
            completion_tokens: Optional[int] = None
    ) -> float:
        """
        Estimate cost for OpenAI model with accurate input/output pricing.

        Args:
            tokens: Total tokens (fallback if split not available)
            model: Model name
            prompt_tokens: Input tokens (if available)
            completion_tokens: Output tokens (if available)

        Returns:
            Estimated cost in USD
        """
        # OpenAI pricing per 1K tokens (as of January 2025)
        # Source: https://openai.com/api/pricing/
        # IMPORTANT: Order matters! Check specific models before generic ones
        pricing = {
            "gpt-4o-mini": {           # Must be before "gpt-4o"
                "input": 0.00015,      # $0.15 per 1M tokens
                "output": 0.0006       # $0.60 per 1M tokens
            },
            "gpt-4o": {
                "input": 0.0025,       # $2.50 per 1M tokens
                "output": 0.010        # $10.00 per 1M tokens
            },
            "gpt-4-turbo": {
                "input": 0.010,        # $10.00 per 1M tokens
                "output": 0.030        # $30.00 per 1M tokens
            },
            "gpt-4": {
                "input": 0.030,        # $30.00 per 1M tokens
                "output": 0.060        # $60.00 per 1M tokens
            },
            "gpt-3.5-turbo": {
                "input": 0.0005,       # $0.50 per 1M tokens
                "output": 0.0015       # $1.50 per 1M tokens
            },
        }

        # Find model pricing (order matters - specific before generic)
        model_pricing = None
        for prefix, rates in pricing.items():
            if model.startswith(prefix):
                model_pricing = rates
                break

        # Default to GPT-4 pricing if unknown
        if not model_pricing:
            model_pricing = {"input": 0.030, "output": 0.060}

        # Calculate accurate cost if we have the split
        if prompt_tokens is not None and completion_tokens is not None:
            input_cost = (prompt_tokens / 1000) * model_pricing["input"]
            output_cost = (completion_tokens / 1000) * model_pricing["output"]
            return input_cost + output_cost

        # Fallback: estimate with blended rate
        # Assume typical ratio: 30% input, 70% output
        blended_rate = (model_pricing["input"] * 0.3) + (model_pricing["output"] * 0.7)
        return (tokens / 1000) * blended_rate

    def calculate_confidence(
            self,
            response: str,
            metadata: Optional[Dict[str, Any]] = None
    ) -> float:
        """
        Calculate confidence score for OpenAI response.

        Uses finish_reason and response length as heuristics.

        Args:
            response: Model response text
            metadata: Response metadata from API

        Returns:
            Confidence score (0-1)
        """
        # Start with base confidence from response analysis
        confidence = super().calculate_confidence(response)

        if metadata:
            # Adjust based on finish_reason
            finish_reason = metadata.get("finish_reason")

            if finish_reason == "stop":
                # Natural completion - strong signal of quality
                # Boost confidence significantly since model chose to stop
                confidence = min(1.0, confidence + 0.4)
            elif finish_reason == "length":
                # Hit max tokens - might be incomplete
                confidence = max(0.5, confidence - 0.1)
            elif finish_reason == "content_filter":
                # Content filtered - low confidence
                confidence = 0.3

        return confidence

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.client.aclose()