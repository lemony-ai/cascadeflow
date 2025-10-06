"""Groq provider implementation with logprobs support."""

import os
import time
from typing import Optional, Dict, Any

import httpx

from .base import BaseProvider, ModelResponse
from ..exceptions import ProviderError, ModelError


class GroqProvider(BaseProvider):
    """
    Groq provider for fast LLM inference.

    Supports: Llama 3.1, Llama 3.2, Mixtral, Gemma models
    Free tier: 14,400 requests per day
    Logprobs: Uses fallback estimation (Groq doesn't support native logprobs)

    NOTE: Despite using OpenAI-compatible API, Groq does NOT support
    logprobs with their models. We use fallback estimation instead.

    Example:
        >>> provider = GroqProvider(api_key="gsk_...")
        >>>
        >>> # Basic completion
        >>> response = await provider.complete(
        ...     prompt="What is AI?",
        ...     model="llama-3.1-8b-instant"
        ... )
        >>> print(response.content)
        >>>
        >>> # With logprobs (estimated, not real)
        >>> response = await provider.complete(
        ...     prompt="The capital of France is",
        ...     model="llama-3.1-8b-instant",
        ...     logprobs=True,
        ...     top_logprobs=5
        ... )
        >>> print(f"Tokens: {response.tokens}")
        >>> print(f"Logprobs: {response.logprobs} (estimated)")
        >>> print(f"Confidence: {response.confidence}")
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Groq provider.

        Args:
            api_key: Groq API key. If None, reads from GROQ_API_KEY env var.
        """
        super().__init__(api_key)
        self.base_url = "https://api.groq.com/openai/v1"

        # Initialize HTTP client
        self.client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            timeout=60.0
        )

    def _load_api_key(self) -> Optional[str]:
        """Load API key from environment."""
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError(
                "Groq API key not found. Please set GROQ_API_KEY environment "
                "variable or pass api_key parameter. Get free key at: "
                "https://console.groq.com"
            )
        return api_key

    def supports_logprobs(self) -> bool:
        """
        Check if provider supports native logprobs.

        NOTE: Despite using OpenAI-compatible API, Groq does NOT support
        logprobs with their models. We use fallback estimation instead.

        Returns:
            False - Groq does not support native logprobs (uses fallback)
        """
        return False

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
        Complete a prompt using Groq API.

        Groq uses OpenAI-compatible API format but does NOT support logprobs.
        When logprobs are requested, we use fallback estimation instead.

        Args:
            prompt: User prompt
            model: Model name (e.g., 'llama-3.1-8b-instant', 'llama-3.1-70b-versatile')
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-2)
            system_prompt: Optional system prompt
            **kwargs: Additional parameters including:
                - logprobs (bool): Include log probabilities (estimated)
                - top_logprobs (int): Number of top logprobs to return

        Returns:
            ModelResponse with standardized format (with estimated logprobs if requested)

        Raises:
            ProviderError: If API call fails
            ModelError: If model execution fails

        Example:
            >>> # Request logprobs (will use fallback estimation)
            >>> result = await provider.complete(
            ...     prompt="Hello",
            ...     model="llama-3.1-8b-instant",
            ...     logprobs=True,
            ...     top_logprobs=5
            ... )
            >>> print(f"Tokens: {result.tokens}")
            >>> print(f"Estimated logprobs: {result.logprobs}")
        """
        start_time = time.time()

        # Extract logprobs parameters (but don't send to API - Groq doesn't support them)
        request_logprobs = kwargs.pop('logprobs', False)
        top_logprobs_count = kwargs.pop('top_logprobs', 5)

        # Build messages (OpenAI format)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Build request payload
        # NOTE: We do NOT add logprobs to payload - Groq doesn't support it
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

            # Extract response (OpenAI format)
            choice = data["choices"][0]
            content = choice["message"]["content"]
            tokens_used = data["usage"]["total_tokens"]

            # Calculate latency
            latency_ms = (time.time() - start_time) * 1000

            # Calculate cost (Groq is free tier)
            cost = self.estimate_cost(tokens_used, model)

            # Build metadata
            metadata = {
                "finish_reason": choice["finish_reason"],
                "prompt_tokens": data["usage"]["prompt_tokens"],
                "completion_tokens": data["usage"]["completion_tokens"],
            }

            # Calculate confidence
            confidence = self.calculate_confidence(content, data)

            # Create base response
            response_obj = ModelResponse(
                content=content,
                model=model,
                provider="groq",
                cost=cost,
                tokens_used=tokens_used,
                confidence=confidence,
                latency_ms=latency_ms,
                metadata=metadata
            )

            # Add logprobs via fallback if requested
            if request_logprobs:
                response_obj = self.add_logprobs_fallback(
                    response=response_obj,
                    temperature=temperature
                )

            return response_obj

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise ProviderError(
                    "Invalid Groq API key. Get free key at: https://console.groq.com",
                    provider="groq",
                    original_error=e
                )
            elif e.response.status_code == 429:
                raise ProviderError(
                    "Groq rate limit exceeded (14,400 requests/day)",
                    provider="groq",
                    original_error=e
                )
            elif e.response.status_code == 400:
                # Extract error message from response
                try:
                    error_data = e.response.json()
                    error_message = error_data.get("error", {}).get("message", str(e))
                    raise ProviderError(
                        f"Groq API error: {error_message}",
                        provider="groq",
                        original_error=e
                    )
                except:
                    raise ProviderError(
                        f"Groq API error: {e.response.status_code}",
                        provider="groq",
                        original_error=e
                    )
            else:
                raise ProviderError(
                    f"Groq API error: {e.response.status_code}",
                    provider="groq",
                    original_error=e
                )
        except httpx.RequestError as e:
            raise ProviderError(
                "Failed to connect to Groq API. Check your internet connection.",
                provider="groq",
                original_error=e
            )
        except (KeyError, IndexError) as e:
            raise ModelError(
                f"Failed to parse Groq response: {e}",
                model=model,
                provider="groq"
            )

    def estimate_cost(self, tokens: int, model: str) -> float:
        """
        Estimate cost for Groq model.

        Groq offers free tier with rate limits (14,400 requests/day).

        Args:
            tokens: Total tokens
            model: Model name

        Returns:
            Estimated cost in USD (0.0 for free tier)
        """
        # Groq pricing (as of 2024)
        # Free tier for all models with rate limits
        rates = {
            "llama-3.1-8b-instant": 0.0,
            "llama-3.1-70b-versatile": 0.0,
            "llama-3.2-1b-preview": 0.0,
            "llama-3.2-3b-preview": 0.0,
            "llama-3.2-11b-vision-preview": 0.0,
            "llama-3.2-90b-vision-preview": 0.0,
            "llama-guard-3-8b": 0.0,
            "mixtral-8x7b-32768": 0.0,
            "gemma-7b-it": 0.0,
            "gemma2-9b-it": 0.0,
        }

        # Find matching rate
        for model_prefix, rate in rates.items():
            if model.startswith(model_prefix):
                return rate

        # Default to free (Groq is free tier)
        return 0.0

    def calculate_confidence(
            self,
            response: str,
            metadata: Optional[Dict[str, Any]] = None
    ) -> float:
        """
        Calculate confidence score for Groq response.

        Args:
            response: Model response text
            metadata: Response metadata from API

        Returns:
            Confidence score (0-1)
        """
        # Start with base confidence
        confidence = super().calculate_confidence(response)

        if metadata:
            # Adjust based on finish_reason
            finish_reason = metadata.get("choices", [{}])[0].get("finish_reason")

            if finish_reason == "stop":
                # Natural completion - good confidence
                confidence = min(1.0, confidence + 0.1)
            elif finish_reason == "length":
                # Hit max tokens - might be incomplete
                confidence = max(0.5, confidence - 0.1)

        return confidence

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.client.aclose()