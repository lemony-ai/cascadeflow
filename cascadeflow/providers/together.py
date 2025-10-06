"""Together.ai provider implementation."""

import os
import time
import math
from typing import Optional, Dict, Any

import httpx

from .base import BaseProvider, ModelResponse
from ..exceptions import ProviderError, ModelError


class TogetherProvider(BaseProvider):
    """
    Together.ai provider.

    Supports 50+ optimized open-source models.
    OpenAI-compatible API with full logprobs support.

    Example:
        >>> provider = TogetherProvider(api_key="...")
        >>> response = await provider.complete(
        ...     prompt="What is AI?",
        ...     model="meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo"
        ... )

        >>> # With logprobs
        >>> response = await provider.complete(
        ...     prompt="What is AI?",
        ...     model="meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
        ...     logprobs=True,
        ...     top_logprobs=10
        ... )
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Together.ai provider.

        Args:
            api_key: Together.ai API key. If None, reads from TOGETHER_API_KEY env var.
        """
        super().__init__(api_key)
        self.base_url = "https://api.together.xyz/v1"

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
        api_key = os.getenv("TOGETHER_API_KEY")
        if not api_key:
            raise ValueError(
                "Together.ai API key not found. Please set TOGETHER_API_KEY environment "
                "variable or pass api_key parameter."
            )
        return api_key

    def _check_logprobs_support(self) -> bool:
        """Together.ai supports logprobs (OpenAI-compatible)."""
        return True

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
        Complete a prompt using Together.ai API.

        Args:
            prompt: User prompt
            model: Model name (e.g., 'meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo')
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-1)
            system_prompt: Optional system prompt
            **kwargs: Additional Together.ai parameters
                     NEW: logprobs (bool) - Enable logprobs
                          top_logprobs (int) - Get top-k alternatives (1-20)

        Returns:
            ModelResponse with standardized format (enhanced with logprobs)

        Raises:
            ProviderError: If API call fails
            ModelError: If model execution fails
        """
        start_time = time.time()

        # Extract logprobs parameters
        logprobs_enabled = kwargs.pop('logprobs', False)
        top_logprobs = kwargs.pop('top_logprobs', None)

        # Build messages (OpenAI-compatible)
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

        # Add logprobs if requested (OpenAI-compatible)
        if logprobs_enabled:
            payload["logprobs"] = True
            if top_logprobs:
                payload["top_logprobs"] = min(top_logprobs, 20)

        try:
            # Make API request
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                json=payload
            )
            response.raise_for_status()

            data = response.json()

            # Extract response (OpenAI-compatible format)
            choice = data["choices"][0]
            content = choice["message"]["content"]
            tokens_used = data["usage"]["total_tokens"]

            # Calculate latency
            latency_ms = (time.time() - start_time) * 1000

            # Calculate cost
            cost = self.estimate_cost(tokens_used, model)

            # Calculate confidence
            confidence = self.calculate_confidence(content, data)

            # Build base response
            model_response = ModelResponse(
                content=content,
                model=model,
                provider="together",
                cost=cost,
                tokens_used=tokens_used,
                confidence=confidence,
                latency_ms=latency_ms,
                metadata={
                    "finish_reason": choice["finish_reason"],
                    "prompt_tokens": data["usage"]["prompt_tokens"],
                    "completion_tokens": data["usage"]["completion_tokens"],
                }
            )

            # Parse logprobs if available (OpenAI-compatible format)
            if logprobs_enabled and "logprobs" in choice and choice["logprobs"]:
                logprobs_data = choice["logprobs"]

                if "content" in logprobs_data and logprobs_data["content"]:
                    tokens = []
                    logprobs_list = []
                    top_logprobs_list = []

                    for token_data in logprobs_data["content"]:
                        # Extract token
                        tokens.append(token_data["token"])

                        # Extract logprob
                        logprobs_list.append(token_data["logprob"])

                        # Extract top alternatives
                        if "top_logprobs" in token_data and token_data["top_logprobs"]:
                            top_k = {}
                            for alt in token_data["top_logprobs"]:
                                top_k[alt["token"]] = alt["logprob"]
                            top_logprobs_list.append(top_k)
                        else:
                            top_logprobs_list.append({})

                    # Add to response
                    model_response.tokens = tokens
                    model_response.logprobs = logprobs_list
                    model_response.top_logprobs = top_logprobs_list

                    # Update confidence based on actual probabilities
                    if logprobs_list:
                        avg_prob = sum(math.exp(lp) for lp in logprobs_list) / len(logprobs_list)
                        # Blend with heuristic confidence
                        model_response.confidence = (confidence + avg_prob) / 2

                    # Add metadata
                    model_response.metadata["has_logprobs"] = True
                    model_response.metadata["estimated"] = False
            else:
                # No logprobs available - add estimated values
                if logprobs_enabled:
                    model_response = self.add_logprobs_fallback(
                        model_response,
                        temperature,
                        base_confidence=0.82  # Together.ai models are good quality
                    )

            return model_response

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise ProviderError(
                    "Invalid Together.ai API key",
                    provider="together",
                    original_error=e
                )
            elif e.response.status_code == 429:
                raise ProviderError(
                    "Together.ai rate limit exceeded",
                    provider="together",
                    original_error=e
                )
            else:
                raise ProviderError(
                    f"Together.ai API error: {e.response.status_code}",
                    provider="together",
                    original_error=e
                )
        except httpx.RequestError as e:
            raise ProviderError(
                "Failed to connect to Together.ai API",
                provider="together",
                original_error=e
            )
        except (KeyError, IndexError) as e:
            raise ModelError(
                f"Failed to parse Together.ai response: {e}",
                model=model,
                provider="together"
            )

    def estimate_cost(self, tokens: int, model: str) -> float:
        """
        Estimate cost for Together.ai models.

        Args:
            tokens: Total tokens
            model: Model name

        Returns:
            Estimated cost in USD
        """
        # Together.ai pricing (approximate, check their pricing page)
        # Varies by model size

        # Rough estimates:
        if "405B" in model or "70B" in model:
            # Large models: ~$0.0008/1K tokens
            return (tokens / 1000) * 0.0008
        elif "13B" in model or "8B" in model:
            # Medium models: ~$0.0002/1K tokens
            return (tokens / 1000) * 0.0002
        else:
            # Small models: ~$0.0001/1K tokens
            return (tokens / 1000) * 0.0001

    def calculate_confidence(
            self,
            response: str,
            metadata: Optional[Dict[str, Any]] = None
    ) -> float:
        """
        Calculate confidence score for Together.ai response.

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
                confidence = min(1.0, confidence + 0.1)
            elif finish_reason == "length":
                confidence = max(0.5, confidence - 0.1)

        return confidence

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.client.aclose()